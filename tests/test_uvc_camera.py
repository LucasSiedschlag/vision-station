from pathlib import Path

import cv2
import numpy as np
import pytest
import yaml

from vision_station.cameras import CameraError, SettingStatus
from vision_station.cameras.uvc import (
    ControlError,
    ControlRange,
    UvcCamera,
    exposure_raw_to_us,
    exposure_us_to_raw,
)
from vision_station.jobs import CameraProfile

FIXTURES = Path(__file__).parent / "fixtures"

C920_RANGES = {
    "exposure": ControlRange(-11, -2, 1),
    "gain": ControlRange(0, 255, 1),
    "white_balance": ControlRange(2000, 6500, 10),
    "focus": ControlRange(0, 250, 5),
    "zoom": ControlRange(100, 500, 1),
    "power_line_frequency": ControlRange(0, 2, 1),
}


class FakeControls:
    """Behaves like the C920 firmware: a value written while the control is in auto is ignored."""

    def __init__(self, ranges=None, ignore=()):
        self.ranges = dict(C920_RANGES if ranges is None else ranges)
        self.state = {n: (r.min, True) for n, r in self.ranges.items()}  # name -> (value, is_auto)
        self.ignore = set(ignore)  # controls whose writes are silently dropped
        self.log = []
        self.closed = False

    def range(self, name):
        return self.ranges.get(name)

    def get(self, name):
        if name not in self.state:
            raise ControlError(f"no {name}")
        return self.state[name]

    def set(self, name, value, auto):
        self.log.append((name, value, auto))
        if name in self.ignore:
            return
        _, was_auto = self.state[name]
        if was_auto and not auto:
            # manual value ignored on the first write: only the mode changes
            self.state[name] = (self.state[name][0], False)
            return
        self.state[name] = (value, auto)

    def close(self):
        self.closed = True


class FakeCapture:
    def __init__(self, accept_size=True):
        self.props = {}
        self.calls = []
        self.accept_size = accept_size
        self.released = False
        self.frames_left = 3

    def isOpened(self):  # noqa: N802
        return not self.released

    def set(self, prop, value):
        self.calls.append(prop)
        if prop in (cv2.CAP_PROP_FRAME_WIDTH, cv2.CAP_PROP_FRAME_HEIGHT) and not self.accept_size:
            return False
        self.props[prop] = value
        return True

    def get(self, prop):
        return self.props.get(prop, 0)

    def read(self):
        if self.frames_left <= 0:
            return False, None
        self.frames_left -= 1
        return True, np.zeros((4, 4, 3), np.uint8)

    def release(self):
        self.released = True


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        self.t += 0.1
        return self.t


@pytest.fixture
def profile():
    """The documented example, without the zoom (that value is for a motorized lens)."""
    full = CameraProfile.model_validate(yaml.safe_load((FIXTURES / "profile.yaml").read_text()))
    return full.model_copy(update={"zoom": None})


class Captures:
    """Hands out a new capture on every open, like cv2.VideoCapture; `last` is the current one."""

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.last = None

    def __call__(self, index):
        self.last = FakeCapture(**self.kwargs)
        return self.last


def make_camera(controls=None, captures=None, sleeps=None):
    controls = controls or FakeControls()
    captures = captures or Captures()
    cam = UvcCamera(
        controls_factory=lambda conn: (controls, 0),
        capture_factory=captures,
        clock=Clock(),
        sleep=(sleeps.append if sleeps is not None else lambda s: None),
    )
    cam.open({"device_name": "C920"})
    return cam, controls, captures


def test_exposure_conversion():
    rng = C920_RANGES["exposure"]
    assert exposure_us_to_raw(8000, rng) == -7
    assert exposure_raw_to_us(-7, rng) == pytest.approx(7812.5)
    # a unit that reports a positive range counts in 100 us steps
    assert exposure_us_to_raw(8000, ControlRange(3, 2047)) == 80
    assert exposure_raw_to_us(80, ControlRange(3, 2047)) == 8000


def test_apply_sets_everything_and_reads_it_back(profile):
    cam, controls, _ = make_camera()
    report = cam.apply(profile)
    assert report.ok, report.failed()
    assert controls.state["exposure"] == (-7, False)
    assert controls.state["gain"] == (0, False)
    assert controls.state["white_balance"] == (4500, False)
    assert controls.state["focus"] == (30, False)
    assert controls.state["zoom"][1] is True  # no zoom in the profile: left alone
    assert controls.state["power_line_frequency"] == (2, False)
    assert "7812" in report.detail["exposure"]  # the nearest step is reported, not hidden


def test_two_passes_with_a_wait_between(profile):
    sleeps = []
    cam, controls, _ = make_camera(sleeps=sleeps)
    cam.apply(profile)
    assert sleeps == [0.2]
    # pass 1 puts the mode on manual with the value it had; pass 2 writes the wanted value
    first = [e for e in controls.log if e[0] == "focus"]
    assert first == [("focus", 0, False), ("focus", 30, False)]


def test_a_write_the_camera_ignores_is_reported_not_hidden(profile):
    cam, _, _ = make_camera(controls=FakeControls(ignore={"focus"}))
    report = cam.apply(profile)
    assert report.status["focus"] is SettingStatus.REJECTED
    assert not report.ok
    assert "kept" in report.detail["focus"]
    assert report.status["gain"] is SettingStatus.APPLIED


def test_missing_control_is_not_supported(profile):
    ranges = {k: v for k, v in C920_RANGES.items() if k != "focus"}
    cam, _, _ = make_camera(controls=FakeControls(ranges=ranges))
    report = cam.apply(profile)
    assert report.status["focus"] is SettingStatus.NOT_SUPPORTED
    assert not report.ok


def test_value_outside_the_range_is_rejected_not_clamped(profile):
    profile = profile.model_copy(update={"white_balance": profile.white_balance.model_copy(update={"kelvin": 9000})})
    cam, controls, _ = make_camera()
    report = cam.apply(profile)
    assert report.status["white_balance"] is SettingStatus.REJECTED
    assert controls.state["white_balance"][1] is True  # untouched: never wrote a different value


def test_zoom_beyond_the_unit_is_rejected(profile):
    from vision_station.jobs.camera_profile import Zoom

    cam, _, _ = make_camera()
    report = cam.apply(profile.model_copy(update={"zoom": Zoom(value=1200)}))
    assert report.status["zoom"] is SettingStatus.REJECTED
    assert "outside" in report.detail["zoom"]


def test_value_is_aligned_to_the_step(profile):
    profile = profile.model_copy(update={"focus": profile.focus.model_copy(update={"value": 32})})
    cam, controls, _ = make_camera()
    assert cam.apply(profile).ok
    assert controls.state["focus"] == (30, False)  # step 5


def test_auto_modes(profile):
    profile = profile.model_copy(update={"exposure": type(profile.exposure)(mode="auto")})
    cam, controls, _ = make_camera()
    report = cam.apply(profile)
    assert report.status["exposure"] is SettingStatus.APPLIED
    assert controls.state["exposure"][1] is True
    assert report.status["low_light_compensation"] is SettingStatus.NOT_SUPPORTED


def test_format_is_forced_before_the_size(profile):
    cam, _, captures = make_camera()
    cam.apply(profile)
    assert captures.last.calls[:3] == [cv2.CAP_PROP_FOURCC, cv2.CAP_PROP_FRAME_WIDTH, cv2.CAP_PROP_FRAME_HEIGHT]


def test_size_the_camera_refuses_is_reported(profile):
    cam, _, _ = make_camera(captures=Captures(accept_size=False))
    report = cam.apply(profile)
    assert report.status["resolution"] is SettingStatus.REJECTED
    assert report.status["pixel_format"] is SettingStatus.APPLIED


def test_read_back_uses_profile_names(profile):
    cam, _, _ = make_camera()
    cam.apply(profile)
    got = cam.read_back()
    assert got["resolution"] == (1920, 1080)
    assert got["pixel_format"] == "mjpeg"
    assert got["exposure"] == {"mode": "manual", "value_us": pytest.approx(7812.5)}
    assert got["white_balance"] == {"mode": "manual", "kelvin": 4500}
    assert got["power_line_hz"] == 60


def test_frames_and_health():
    cam, _, captures = make_camera()
    capture = captures.last
    frames = []
    with pytest.raises(CameraError, match="stopped"):
        for frame in cam.frames():
            frames.append(frame)
    assert len(frames) == 3
    assert frames[0].timestamp < frames[1].timestamp
    health = cam.health()
    assert health.connected and health.fps > 0
    cam.close()
    assert capture.released and not cam.health().connected


def test_snapshot_is_not_offered_and_capabilities_list_what_exists():
    cam, _, _ = make_camera()
    assert cam.snapshot() is None
    caps = cam.capabilities()
    assert not caps.has_snapshot
    assert {"resolution", "exposure", "power_line_hz"} <= caps.settings


def test_not_open_and_open_failure():
    cam = UvcCamera(lambda c: (FakeControls(), 0), lambda i: FakeCapture())
    with pytest.raises(CameraError, match="not open"):
        cam.read_back()
    closed = FakeCapture()
    closed.released = True
    cam = UvcCamera(lambda c: (FakeControls(), 0), lambda i: closed)
    with pytest.raises(CameraError, match="cannot open"):
        cam.open({"device_index": 0})
