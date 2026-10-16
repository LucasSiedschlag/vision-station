from pathlib import Path

import numpy as np
import pytest
import yaml

from vision_station.cameras import ApplyReport, Camera, CameraError, Capabilities, Frame, Health, SettingStatus
from vision_station.jobs import CameraProfile, Job
from vision_station.jobs.job import Trigger
from vision_station.results import InspectionResult, Outcome
from vision_station.station import (
    Acquisition,
    PresenceDetector,
    State,
    StationController,
    VerifyResult,
)
from vision_station.store import JobBundle

FIXTURES = Path(__file__).parent / "fixtures"


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now

    def advance(self, s):
        self.now += s


class FakeCamera(Camera):
    """A live camera: every read returns the current `scene`, stamped with the clock."""

    def __init__(self, clock, scene=None):
        self.clock = clock
        self.scene = scene if scene is not None else empty_scene()
        self.opened = 0
        self.applied = []
        self.status = None  # per-setting status override for apply()
        self.fail_open = False
        self.fail_read = False
        self.open_now = False
        self.flash_frames = 0  # overexposed frames sent after each apply, like the C920 when its capture reopens
        self._flash_left = 0

    def open(self, connection):
        if self.fail_open:
            raise CameraError("camera not found")
        self.opened += 1
        self.open_now = True

    def close(self):
        self.open_now = False

    def capabilities(self):
        return Capabilities()

    def apply(self, profile, raw=None):
        self.applied.append(profile)
        self._flash_left = self.flash_frames
        status = self.status or {"exposure": SettingStatus.APPLIED}
        return ApplyReport(status=status, detail={k: "x" for k in status})

    def read_back(self):
        return {}

    def frames(self):
        while self.open_now:
            if self.fail_read:
                raise CameraError("usb disconnected")
            if self._flash_left > 0:
                self._flash_left -= 1
                yield Frame(np.full_like(self.scene, 240), self.clock())
                continue
            yield Frame(self.scene.copy(), self.clock())

    def snapshot(self):
        return None

    def health(self):
        return Health(self.open_now, 0.0, None)


def empty_scene():
    return np.full((120, 160, 3), 90, np.uint8)


def scene_with_object(x=40):
    img = empty_scene()
    img[30:90, x : x + 60] = (20, 20, 25)  # dark enough to differ in gray level
    return img


def make_bundle(mode="image_presence", presence=True, waiting=None) -> JobBundle:
    data = yaml.safe_load((FIXTURES / "job.yaml").read_text(encoding="utf-8"))
    data["geometry"] = {"rois": {"label": {"relative_to": "frame", "rect": [0.2, 0.2, 0.8, 0.5]}}}
    data["tools"] = [{"id": "lote", "type": "code", "version": 1, "roi": "label", "reason_fail": "Código não lido"}]
    data["trigger"] = {"mode": mode, "still_ms": 400, "min_area": 0.05}
    if presence:
        data["trigger"]["presence_roi"] = [0.0, 0.0, 1.0, 1.0]
    if waiting:
        data["ui"] = {"waiting": waiting}
    elif "ui" in data:
        del data["ui"]
    profile = CameraProfile.model_validate(yaml.safe_load((FIXTURES / "profile.yaml").read_text()))
    return JobBundle(job=Job.model_validate(data), profile=profile)


class Rig:
    """Everything wired with a fake clock, advancing time in 0.1 s ticks."""

    def __init__(self, mode="image_presence", presence=True, outcome=Outcome.PASS, settle_s=0.0, **controller_args):
        self.clock = Clock()
        self.camera = FakeCamera(self.clock)
        self.acq = Acquisition(self.camera, {"device_name": "fake"}, clock=self.clock, retry_delays_s=(1.0, 2.0), settle_s=settle_s)
        self.inspected = []
        self.outcome = outcome
        self.events = []
        self.controller = StationController(self.acq, self._inspect, clock=self.clock, on_event=self.events.append, **controller_args)
        self.bundle = make_bundle(mode, presence)

    def _inspect(self, bundle, frame):
        self.inspected.append(frame)
        if isinstance(self.outcome, Exception):
            raise self.outcome
        if callable(self.outcome):
            return self.outcome(frame)
        return InspectionResult(self.outcome, "Tampa ausente" if self.outcome is Outcome.FAIL else "")

    def tick(self, n=1, dt=0.1):
        for _ in range(n):
            self.clock.advance(dt)
            self.acq.step()
            self.controller.step()

    def boot(self, ticks=3):
        self.controller.start(self.bundle)
        self.tick(ticks)
        assert self.controller.state is State.READY, self.controller.status()

    @property
    def state(self):
        return self.controller.state

    def states(self):
        return [e.state for e in self.events if e.kind == "state"]

    def results(self):
        return [e.result for e in self.events if e.kind == "result"]


# --- acquisition -------------------------------------------------------------


def test_acquisition_connects_applies_settings_and_keeps_only_the_latest_frame():
    clock = Clock()
    cam = FakeCamera(clock)
    acq = Acquisition(cam, {}, clock=clock)
    acq.configure(make_bundle().profile)
    clock.advance(1)
    acq.step()
    assert acq.connected and acq.generation == 1 and len(cam.applied) == 1
    assert acq.applied_serial == acq.profile_serial and acq.last_apply.ok
    first = acq.latest()
    clock.advance(1)
    acq.step()
    assert acq.latest().timestamp > first.timestamp
    assert acq.frame_after(first.timestamp) is acq.latest()
    assert acq.frame_after(acq.latest().timestamp) is None  # nothing newer than that moment
    assert not acq.stalled()


def test_acquisition_publishes_frames_only_once_the_camera_settled_after_applying():
    clock = Clock()
    cam = FakeCamera(clock)
    cam.flash_frames = 2
    acq = Acquisition(cam, {}, clock=clock, settle_s=0.5)
    acq.configure(make_bundle().profile)
    acq.step()  # connects, applies, reads a frame inside the settling time
    assert acq.connected and not acq.applied and acq.latest() is None
    for _ in range(4):
        clock.advance(0.1)
        acq.step()
        assert not acq.applied and acq.latest() is None
    clock.advance(0.2)
    acq.step()
    assert acq.applied and acq.latest().image.mean() == pytest.approx(90)  # the scene, not the overexposed frames
    assert not acq.stalled()

    acq.configure(make_bundle().profile)  # a job switch: written again
    clock.advance(0.1)
    acq.step()
    assert not acq.applied and acq.latest() is None  # the frame from before the apply is not used either
    for _ in range(6):
        clock.advance(0.1)
        acq.step()
    assert acq.applied and acq.latest().image.mean() == pytest.approx(90) and len(cam.applied) == 2


def test_acquisition_loses_the_camera_retries_with_growing_delays_and_reapplies_settings():
    clock = Clock()
    cam = FakeCamera(clock)
    acq = Acquisition(cam, {}, clock=clock, retry_delays_s=(1.0, 2.0, 5.0))
    acq.configure(make_bundle().profile)
    acq.step()
    assert acq.connected
    cam.fail_read = True
    acq.step()
    assert not acq.connected and acq.latest() is None and "usb disconnected" in acq.last_error
    assert acq.stalled()
    cam.fail_read = False
    cam.fail_open = True
    attempts = []
    for _ in range(40):  # 0.25 s per tick: the retry waits are 1 s, then 2 s, then 5 s
        clock.advance(0.25)
        before = (clock(), cam.opened)
        acq.step()
        if cam.fail_open and acq._failures > len(attempts) + 1:
            attempts.append(clock())
        if len(attempts) == 2:
            break
    gaps = [round(b - a, 2) for a, b in zip(attempts, attempts[1:])]
    assert gaps and gaps[0] >= 2.0  # the second wait is longer than the first
    cam.fail_open = False
    for _ in range(40):
        clock.advance(0.5)
        acq.step()
    assert acq.connected and acq.generation == 2
    assert len(cam.applied) == 2  # written again on the reconnect (FR-ACQ-5)
    assert acq.latest() is not None


def test_acquisition_detects_a_stall_and_the_end_of_a_stream():
    clock = Clock()
    cam = FakeCamera(clock)
    acq = Acquisition(cam, {}, clock=clock, stall_timeout_s=3.0)
    acq.step()
    assert not acq.stalled()
    clock.advance(3.5)  # the camera hangs: no new frame, but no error either
    assert acq.stalled()

    class Short(FakeCamera):
        def frames(self):
            yield Frame(self.scene.copy(), self.clock())

    short = Acquisition(Short(clock), {}, clock=clock)
    short.step()
    short.step()
    assert not short.connected and "ended" in short.last_error


def test_acquisition_thread_runs_and_stops():
    import time as real

    cam = FakeCamera(real.monotonic)
    acq = Acquisition(cam, {}, clock=real.monotonic)
    acq.start()
    deadline = real.monotonic() + 2
    while acq.latest() is None and real.monotonic() < deadline:
        real.sleep(0.01)
    assert acq.latest() is not None
    acq.stop()
    assert not acq.connected


# --- presence ----------------------------------------------------------------


def trigger(**kw):
    return Trigger.model_validate({"presence_roi": [0, 0, 1, 1], "still_ms": 400, **kw})


def test_presence_motion_and_stillness():
    det = PresenceDetector(trigger())
    assert not det.update(empty_scene(), 0.0).present
    p = det.update(scene_with_object(40), 0.1)
    assert p.present and p.moving and p.still_for_s == 0.0
    p = det.update(scene_with_object(42), 0.2)  # sliding into place
    assert p.moving and p.still_for_s == 0.0
    det.update(scene_with_object(42), 0.3)
    p = det.update(scene_with_object(42), 0.8)
    assert p.present and not p.moving and p.still_for_s == pytest.approx(0.5)
    p = det.update(empty_scene(), 0.9)
    assert not p.present
    assert det.update(empty_scene(), 1.4).absent_for_s == pytest.approx(0.5)


def test_presence_uses_only_the_region_and_follows_slow_light_changes():
    det = PresenceDetector(trigger(presence_roi=[0.0, 0.0, 0.2, 1.0]))
    det.update(empty_scene(), 0.0)
    assert not det.update(scene_with_object(100), 0.1).present  # the object is outside the region
    det2 = PresenceDetector(trigger())
    scene = empty_scene()
    det2.update(scene, 0.0)
    for i in range(1, 200):  # the light gets brighter by 1 level every few frames
        brighter = np.clip(scene.astype(int) + i // 4, 0, 255).astype(np.uint8)
        assert not det2.update(brighter, i * 0.1).present
    assert det2.update(scene_with_object(40), 30.0).present


def test_a_small_change_is_not_presence_and_reset_forgets_the_scene():
    det = PresenceDetector(trigger(min_area=0.3))
    det.update(empty_scene(), 0.0)
    assert not det.update(scene_with_object(40), 0.1).present  # the object covers about 19%
    det.reset_background()
    assert not det.update(scene_with_object(40), 0.2).present  # taken as the empty scene


# --- the controller ----------------------------------------------------------


def test_one_inspection_per_box_through_the_whole_cycle():
    rig = Rig()
    rig.boot()
    assert rig.controller.status().message == "Aguardando objeto"
    rig.camera.scene = scene_with_object(40)
    rig.tick(2)
    assert rig.state is State.WAITING_STILL
    rig.tick(8)  # still for 0.8 s
    assert rig.state is State.SHOWING_RESULT and len(rig.inspected) == 1
    assert rig.controller.last_result.outcome is Outcome.PASS
    rig.tick(30)  # the object stays in place for 3 s
    assert len(rig.inspected) == 1 and rig.state is State.SHOWING_RESULT  # not inspected again (FR-TRG-4)
    rig.camera.scene = empty_scene()
    rig.tick(6)
    assert rig.state is State.READY
    rig.camera.scene = scene_with_object(60)  # the next object
    rig.tick(12)
    assert len(rig.inspected) == 2
    assert rig.states()[:6] == [State.PREPARING, State.READY, State.WAITING_STILL, State.INSPECTING, State.SHOWING_RESULT, State.READY]


def test_a_job_switch_does_not_take_the_overexposed_frames_after_applying_as_the_empty_scene():
    """VIA-0045: the C920 sends a few overexposed frames after each apply. Taken as the empty scene, the
    real scene looked like an object forever: the station inspected on its own and never re-armed."""
    rig = Rig(settle_s=0.5)
    rig.camera.flash_frames = 2
    rig.boot(ticks=8)
    rig.controller.switch_job(rig.bundle)
    rig.tick(20)
    assert rig.state is State.READY and rig.inspected == []
    rig.camera.scene = scene_with_object(40)
    rig.tick(10)
    assert len(rig.inspected) == 1
    rig.camera.scene = empty_scene()
    rig.tick(6)
    assert rig.state is State.READY  # re-armed


def test_the_inspected_frame_was_captured_after_the_trigger():
    rig = Rig()
    triggers = []
    original = rig._inspect
    rig._inspect = lambda bundle, frame: (triggers.append(rig.controller._t0), original(bundle, frame))[1]
    rig.controller._inspect = rig._inspect
    rig.boot()
    rig.camera.scene = scene_with_object(40)
    rig.tick(10)
    assert len(rig.inspected) == 1
    assert rig.inspected[0].timestamp > triggers[0]


def test_a_box_that_leaves_before_it_is_still_is_not_inspected():
    rig = Rig()
    rig.boot()
    rig.camera.scene = scene_with_object(40)
    rig.tick(2)
    assert rig.state is State.WAITING_STILL
    rig.camera.scene = empty_scene()
    rig.tick(3)
    assert rig.state is State.READY and rig.inspected == []


def test_fail_and_error_results_are_shown_with_the_reason():
    rig = Rig(outcome=Outcome.FAIL)
    rig.boot()
    rig.camera.scene = scene_with_object()
    rig.tick(10)
    assert rig.state is State.SHOWING_RESULT
    assert rig.controller.status().message == "FAIL: Tampa ausente"


@pytest.mark.parametrize(
    "outcome",
    [RuntimeError("boom"), lambda f: "PASS", lambda f: InspectionResult("MAYBE"), lambda f: None],
)
def test_an_internal_error_or_bad_result_is_an_error_never_a_pass(outcome):
    rig = Rig(outcome=outcome)
    rig.boot()
    rig.camera.scene = scene_with_object()
    rig.tick(10)
    assert rig.controller.last_result.outcome is Outcome.ERROR
    assert Outcome.PASS not in [r.outcome for r in rig.results()]


def test_the_camera_lost_during_an_inspection_is_an_error():
    def lose_camera(frame):
        rig.camera.fail_read = True
        rig.tick(1)  # the camera drops while the pipeline runs
        return InspectionResult(Outcome.PASS)

    rig = Rig(outcome=lose_camera)
    rig.boot()
    rig.camera.scene = scene_with_object()
    rig.tick(10)
    assert rig.controller.last_result.outcome is Outcome.ERROR
    assert "Câmera" in rig.controller.last_result.reason
    assert rig.state is State.CAMERA_LOST


def test_a_missing_fresh_frame_ends_in_error_after_the_timeout():
    rig = Rig(inspect_timeout_s=1.0)
    rig.boot()
    rig.acq.step = lambda: None  # no new frames arrive from now on (but the camera is not declared lost yet)
    rig.controller.request_trigger()
    rig.tick(15)
    assert rig.inspected == []  # the buffered frame from before the trigger is never used
    assert rig.controller.last_result.outcome is Outcome.ERROR
    assert rig.controller.last_result.reason == "Imagem não recebida da câmera"


def test_camera_lost_and_recovered_goes_back_through_preparing():
    rig = Rig()
    rig.boot()
    applied_before = len(rig.camera.applied)
    rig.camera.fail_read = True
    rig.tick(2)
    assert rig.state is State.CAMERA_LOST
    assert rig.controller.status().message == "Câmera desconectada"
    rig.camera.fail_read = False
    rig.tick(40, dt=0.1)
    assert rig.state is State.READY
    assert len(rig.camera.applied) == applied_before + 1  # settings written again on reconnect
    assert State.PREPARING in rig.states()[rig.states().index(State.CAMERA_LOST) :]


def test_starting_with_the_camera_unplugged_waits_then_continues():
    rig = Rig()
    rig.camera.fail_open = True
    rig.controller.start(rig.bundle)
    rig.tick(5)
    assert rig.state is State.CAMERA_LOST
    rig.camera.fail_open = False
    rig.tick(60)
    assert rig.state is State.READY


def test_a_setting_the_camera_refused_stops_in_fault_until_retry():
    rig = Rig()
    rig.camera.status = {"exposure": SettingStatus.REJECTED, "gain": SettingStatus.APPLIED}
    rig.controller.start(rig.bundle)
    rig.tick(4)
    assert rig.state is State.FAULT
    assert "exposure" in rig.controller.status().detail
    assert rig.controller.status().message == "Falha na verificação — chamar manutenção"
    rig.camera.scene = scene_with_object()
    rig.tick(20)
    assert rig.state is State.FAULT and rig.inspected == []  # no inspection while faulted
    rig.camera.status = {"exposure": SettingStatus.APPLIED}
    rig.controller.retry()
    rig.tick(4)
    assert rig.state is State.READY


def test_unsupported_settings_are_warnings_not_a_fault():
    rig = Rig()
    rig.camera.status = {"exposure": SettingStatus.APPLIED, "zoom": SettingStatus.NOT_SUPPORTED}
    rig.boot()
    assert any("zoom" in w for w in rig.controller.status().warnings)


def test_the_verifier_can_refuse_a_job():
    rig = Rig()
    rig.controller._verify = lambda bundle, acq: VerifyResult(False, "imagem diferente da referência")
    rig.controller.start(rig.bundle)
    rig.tick(4)
    assert rig.state is State.FAULT and rig.controller.status().detail == "imagem diferente da referência"


def test_manual_trigger_and_hold_time_without_presence_detection():
    rig = Rig(mode="manual", presence=False, hold_s=1.0)
    rig.boot()
    rig.tick(5)
    assert rig.inspected == []  # nothing starts it
    rig.controller.request_trigger()
    rig.tick(3)
    assert len(rig.inspected) == 1 and rig.state is State.SHOWING_RESULT
    rig.tick(12)
    assert rig.state is State.READY


def test_manual_trigger_also_works_with_presence_detection():
    rig = Rig()
    rig.boot()
    rig.controller.request_trigger()
    rig.tick(3)
    assert len(rig.inspected) == 1


def test_continuous_mode_inspects_frame_after_frame():
    rig = Rig(mode="continuous", presence=False)
    rig.controller.start(rig.bundle)
    rig.tick(25)
    assert len(rig.inspected) >= 5
    stamps = [f.timestamp for f in rig.inspected]
    assert stamps == sorted(stamps) and len(set(stamps)) == len(stamps)


def test_switching_jobs_prepares_again_and_uses_the_job_text():
    rig = Rig()
    rig.boot()
    other = make_bundle(waiting="Aguardando etiqueta")
    rig.controller.switch_job(other)
    rig.tick(1)
    assert rig.state is State.PREPARING
    rig.tick(4)
    assert rig.state is State.READY and rig.controller.status().message == "Aguardando etiqueta"
    assert rig.camera.applied  # the new job's settings were applied


def test_pause_and_resume():
    rig = Rig()
    rig.boot()
    rig.controller.pause()
    rig.tick(1)
    assert rig.state is State.PAUSED and rig.controller.status().message == "Em manutenção"
    rig.camera.scene = scene_with_object()
    rig.tick(15)
    assert rig.inspected == []
    rig.controller.resume()
    rig.tick(4)
    assert rig.state is State.READY


def test_a_pass_only_ever_comes_with_the_inspecting_to_showing_result_path():
    rig = Rig()
    rig.boot()
    for scene in (scene_with_object(30), empty_scene(), scene_with_object(70), empty_scene()):
        rig.camera.scene = scene
        rig.tick(12)
    passes = [i for i, e in enumerate(rig.events) if e.kind == "result" and e.result.outcome is Outcome.PASS]
    assert len(passes) == 2
    for i in passes:
        assert rig.events[i - 1].state is State.INSPECTING  # emitted right after entering from INSPECTING
