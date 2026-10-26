"""The station controller: the state machine of architecture §6.

It is the only component that changes the station's state. One inspection runs at a time. A PASS can
only come out of the `INSPECTING -> SHOWING_RESULT` path, from a fresh frame, with the camera alive
at the end: any doubt (camera lost, stale frame, internal error, unknown outcome) is an ERROR
(FR-INS-6, "never a false PASS").

`step()` does one unit of work, so tests drive it with a fake clock; `run()` calls it in a loop.
Other threads talk to the controller through commands (`request_trigger`, `switch_job`, ...), which
`step()` applies in order.
"""

import logging
import queue
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import Any

from vision_station.cameras import Frame, SettingStatus
from vision_station.core.errors import CATALOG, ErrorCode
from vision_station.core.i18n import tr
from vision_station.core.results import InspectionResult, Outcome, ResultJob, TriggerInfo, TriggerSource
from vision_station.station.acquisition import Acquisition
from vision_station.station.trigger import PresenceDetector
from vision_station.store import JobBundle


log = logging.getLogger(__name__)


class State(StrEnum):
    STARTING = "Starting"
    PREPARING = "Preparing"
    READY = "Ready"
    WAITING_STILL = "WaitingStill"
    INSPECTING = "Inspecting"
    SHOWING_RESULT = "ShowingResult"
    CAMERA_LOST = "CameraLost"
    FAULT = "Fault"
    PAUSED = "Paused"


NO_JOB = tr("Nenhum job ativo — ativar um job na tela Jobs")

# What the operator screen shows (architecture §6). "waiting" can be replaced by the job (`ui.waiting`).
MESSAGES = {
    State.STARTING: tr("Preparando…"),
    State.PREPARING: tr("Preparando…"),
    State.READY: tr("Aguardando objeto"),
    State.WAITING_STILL: tr("Aguardando objeto"),
    State.INSPECTING: tr("Inspecionando…"),
    State.CAMERA_LOST: tr("Câmera desconectada"),
    State.FAULT: tr("Falha na verificação — chamar manutenção"),
    State.PAUSED: tr("Em manutenção"),
}


@dataclass(frozen=True)
class VerifyResult:
    ok: bool
    message: str = ""
    warnings: tuple[str, ...] = ()


Verifier = Callable[[JobBundle, Acquisition], VerifyResult]
Inspector = Callable[[JobBundle, Frame], InspectionResult]


def basic_verifier(bundle: JobBundle, acquisition: Acquisition) -> VerifyResult:
    """Camera settings: every one the camera has must be applied. (The full verification, with the
    reference image and reference set, replaces this one: FR-JOB-9.)"""
    report = acquisition.last_apply
    if report is None:
        return VerifyResult(False, tr("ajustes da câmera não aplicados"))
    rejected = sorted(k for k, s in report.status.items() if s is SettingStatus.REJECTED)
    if rejected:
        return VerifyResult(False, tr("ajuste não aplicado: {settings}", settings=", ".join(rejected)))
    unsupported = tuple(sorted(tr("{setting}: {detail}", setting=k, detail=report.detail.get(k) or tr("não suportado")) for k, s in report.status.items() if s is SettingStatus.NOT_SUPPORTED))
    return VerifyResult(True, warnings=unsupported)


@dataclass(frozen=True)
class StationEvent:
    kind: str  # "state" or "result"
    state: State
    previous: State | None = None
    message: str = ""
    result: InspectionResult | None = None
    frame: Frame | None = None
    # the job that was active, on "result" events, so a recorder needs nothing else
    job_id: str = ""
    job_name: str = ""
    job_version: int = 0
    reference: str = ""  # on "result" events: what the caller gave with the trigger that started it (FR-INT-1)
    showing_result: bool = False  # on "state" events: the last verdict is still to be shown (VIA-0049)


@dataclass
class _Command:
    name: str
    bundle: JobBundle | None = None
    detail: str = ""
    trigger: TriggerInfo | None = None
    active: bool = False  # on "line" commands: the level of the trigger input


@dataclass
class Status:
    state: State
    message: str
    detail: str = ""
    job_name: str = ""
    job_version: int = 0
    last_result: InspectionResult | None = None
    job_id: str = ""
    warnings: tuple[str, ...] = field(default_factory=tuple)
    showing_result: bool = False  # the last verdict is shown, also after the station armed again (VIA-0049)


class StationController:
    def __init__(
        self,
        acquisition: Acquisition,
        inspect: Inspector,
        verifier: Verifier | None = None,
        clock: Callable[[], float] = time.monotonic,
        on_event: Callable[[StationEvent], Any] | None = None,
        hold_s: float = 2.0,
        absent_s: float = 0.3,
        inspect_timeout_s: float = 5.0,
        wall: Callable[[], float] = time.time,
        first_sequence: int = 0,
        save_sequence: Callable[[int], Any] | None = None,
    ):
        self._acq = acquisition
        self._inspect = inspect
        if verifier is None:
            # FR-JOB-9: the default must verify both parts, including required references.
            from vision_station.verification import JobVerifier

            verifier = JobVerifier(inspect)
        self._verify = verifier
        self._clock = clock
        self._on_event = on_event
        self._hold_s = hold_s
        self._absent_s = absent_s
        self._inspect_timeout_s = inspect_timeout_s
        self._wall = wall  # wall-clock time for the result; `clock` is monotonic, like the frames' timestamps
        self._sequence = first_sequence % 2**32  # the next result's number: seeded from the records (R2)
        self._save_sequence = save_sequence  # remembers each number given, recorded or not
        self._job_ref: ResultJob | None = None

        self._commands: queue.Queue[_Command] = queue.Queue()
        self._bundle: JobBundle | None = None
        self._detector: PresenceDetector | None = None
        self._state = State.STARTING
        self._detail = ""
        self._warnings: tuple[str, ...] = ()
        self._last_result: InspectionResult | None = None
        self._trigger_requested = False
        self._trigger_reference = ""
        self._pending_trigger: TriggerInfo | None = None
        self._trigger: TriggerInfo | None = None  # of the inspection running now
        self._trigger_lock = threading.Lock()
        self._trigger_taken = False  # a trigger was accepted and its inspection has not started yet (VIA-0051)
        self._reference = ""  # of the inspection running now
        self._t0 = 0.0  # when the current inspection was triggered
        self._began_at = float("-inf")  # when the last inspection began, for the interval of the continuous mode
        self._shown_at = float("-inf")
        self._showing = False  # what the screens were last told about showing the verdict
        self._last_frame_ts = -1.0
        self._line_active_since: float | None = None  # when the trigger input went active; None while it is not
        self._line_counted = False  # this activation already caused its trigger
        self._stop = threading.Event()

    # --- commands (safe to call from other threads) ------------------------------

    def start(self, bundle: JobBundle) -> None:
        self._commands.put(_Command("load", bundle))

    def switch_job(self, bundle: JobBundle) -> None:
        self._commands.put(_Command("load", bundle))

    def fault(self, detail: str) -> None:
        """Stop in Fault with this reason, e.g. the active job could not be loaded."""
        self._commands.put(_Command("fault", detail=detail))

    def request_trigger(self, reference: str = "", source: TriggerSource = "manual", caller_reference: str = "") -> None:
        """Manual or external trigger (FR-TRG-2/3). `reference` comes back on the result event, so another
        program can tell which result answers its request (FR-INT-1); `caller_reference` is what that program
        gave, kept in the result's trigger."""
        self._commands.put(_Command("trigger", detail=reference, trigger=TriggerInfo(source, caller_reference)))

    def try_request_trigger(self, reference: str = "", source: TriggerSource = "manual", caller_reference: str = "") -> bool:
        """Accept a trigger only if the station is ready and no other trigger is waiting to start: checking and
        taking the turn happen together, so two requests at once are one inspection and one refusal, never two
        accepted with one of them silently dropped (VIA-0051)."""
        with self._trigger_lock:
            if self._trigger_taken or self._state not in (State.READY, State.WAITING_STILL):
                return False
            self._trigger_taken = True
        self.request_trigger(reference, source, caller_reference)
        return True

    def set_line(self, active: bool) -> None:
        """The level of the trigger input, already in the job's sense (the station's input adapter applies the edge and the
        polarity, FR-INT-17). The trigger counts once the input has stayed active for the job's `debounce_ms` (FR-TRG-8);
        a pulse shorter than that is bounce and is ignored. A new trigger needs the input to go inactive first."""
        self._commands.put(_Command("line", active=active))

    def pause(self) -> None:
        self._commands.put(_Command("pause"))

    def resume(self) -> None:
        self._commands.put(_Command("resume"))

    def retry(self) -> None:
        self._commands.put(_Command("retry"))

    def reset_background(self) -> None:
        self._commands.put(_Command("reset_background"))

    # --- reading ------------------------------------------------------------------

    @property
    def state(self) -> State:
        return self._state

    @property
    def last_result(self) -> InspectionResult | None:
        return self._last_result

    @property
    def showing_result(self) -> bool:
        """The verdict stays on the screens for at least hold_s, even when the image trigger already armed
        the station again (nothing in front of the camera): Ready, but still showing it, until the time is
        over or the next inspection starts."""
        if self._last_result is None:
            return False
        if self._state is State.SHOWING_RESULT:
            return True
        return self._state in (State.READY, State.WAITING_STILL) and self._clock() - self._shown_at < self._hold_s

    def set_hold(self, seconds: float) -> None:
        """How long a verdict is shown at least (system.yaml station.result_min_s)."""
        self._hold_s = seconds

    def status(self) -> Status:
        job = self._bundle.job.job if self._bundle else None
        return Status(
            state=self._state,
            message=self._message(),
            detail=self._detail,
            job_name=job.name if job else "",
            job_version=job.version if job else 0,
            job_id=str(job.id) if job else "",
            last_result=self._last_result,
            warnings=self._warnings,
            showing_result=self.showing_result,
        )

    def _message(self) -> str:
        if self.showing_result and self._last_result is not None:
            r = self._last_result
            return tr("{outcome}: {reason}", outcome=r.outcome, reason=r.reason) if r.reason else str(r.outcome)
        if self._state is State.STARTING and self._bundle is None:
            return NO_JOB
        waiting = self._bundle.job.ui.waiting if self._bundle else None
        if self._state in (State.READY, State.WAITING_STILL) and waiting and (waiting.pt_br or waiting.en):
            return waiting.filled()
        return MESSAGES[self._state]

    # --- the loop -------------------------------------------------------------------

    def run(self, period_s: float = 0.02) -> None:
        while not self._stop.is_set():
            self.step()
            self._stop.wait(period_s)

    def stop(self) -> None:
        self._stop.set()

    def step(self) -> None:
        while True:
            try:
                command = self._commands.get_nowait()
            except queue.Empty:
                break
            self._apply_command(command)

        state = self._state
        if state in (State.STARTING, State.FAULT, State.PAUSED):
            return
        self._count_line()
        if state is not State.CAMERA_LOST and self._acq.stalled():
            self._camera_lost()
            return
        handler = {
            State.PREPARING: self._preparing,
            State.READY: self._ready,
            State.WAITING_STILL: self._waiting_still,
            State.INSPECTING: self._inspecting,
            State.SHOWING_RESULT: self._showing_result,
            State.CAMERA_LOST: self._camera_lost_wait,
        }[state]
        handler()
        if self.showing_result != self._showing:  # the held verdict ended without a change of state
            self._showing = self.showing_result
            self._emit(StationEvent("state", self._state, previous=self._state, message=self._message(), showing_result=self._showing))

    # --- commands -------------------------------------------------------------------

    def _apply_command(self, command: _Command) -> None:
        if command.name == "load" and command.bundle is not None:
            self._load(command.bundle)
        elif command.name == "trigger":
            self._trigger_requested = True
            self._trigger_reference = command.detail
            self._pending_trigger = command.trigger
        elif command.name == "line":
            if not command.active:
                self._line_active_since, self._line_counted = None, False
            elif self._line_active_since is None:
                self._line_active_since = self._clock()
        elif command.name == "pause" and self._state in (State.READY, State.WAITING_STILL, State.SHOWING_RESULT):
            self._go(State.PAUSED)
        elif command.name == "resume" and self._state is State.PAUSED:
            self._prepare()
        elif command.name == "retry" and self._state is State.FAULT and self._bundle is not None:
            self._prepare()
        elif command.name == "fault":
            self._detail = command.detail
            self._go(State.FAULT)
        elif command.name == "reset_background" and self._detector is not None:
            self._detector.reset_background()

    def _load(self, bundle: JobBundle) -> None:
        if self._state is State.INSPECTING:
            self._finish(self._error(ErrorCode.JOB_SWITCHED), None)
        self._bundle = bundle
        info = bundle.job.job
        self._job_ref = ResultJob(str(info.id), info.name, info.version, content_hash=bundle.content_hash)
        trigger = bundle.job.acquisition.trigger
        self._detector = PresenceDetector(trigger.image_presence) if trigger.type == "image_presence" and trigger.image_presence else None
        self._prepare()

    def _prepare(self) -> None:
        assert self._bundle is not None
        self._trigger_requested = False
        self._trigger_reference = ""
        self._pending_trigger = None
        with self._trigger_lock:
            self._trigger_taken = False  # a trigger accepted before is dropped with the preparation
        self._shown_at = float("-inf")  # a verdict from before is not shown again after preparing
        self._acq.configure(self._bundle.profile)
        self._detail = ""
        self._go(State.PREPARING)

    def _count_line(self) -> None:
        """The trigger input has stayed active long enough (FR-TRG-8): it becomes a trigger from the machine."""
        if self._line_active_since is None or self._line_counted or self._bundle is None:
            return
        trigger = self._bundle.job.acquisition.trigger
        if trigger.type != "external" or trigger.external is None or self._state not in (State.READY, State.WAITING_STILL):
            return
        if self._clock() - self._line_active_since < trigger.external.debounce_ms / 1000:
            return
        self._line_counted = True
        if not self._trigger_requested:
            with self._trigger_lock:
                self._trigger_taken = True
            self._trigger_requested = True
            self._pending_trigger = TriggerInfo("machine")

    # --- state handlers -----------------------------------------------------------

    def _preparing(self) -> None:
        acq = self._acq
        if acq.applied_serial != acq.profile_serial or acq.latest() is None:
            return  # still applying the settings or waiting for the first frame
        result = self._verify(self._bundle, acq)  # type: ignore[arg-type]
        self._warnings = result.warnings
        if not result.ok:
            self._detail = result.message
            self._go(State.FAULT)
            return
        if self._detector is not None:
            self._detector.reset_background()
        self._go(State.READY)

    def _new_frame(self) -> Frame | None:
        frame = self._acq.latest()
        if frame is None or frame.timestamp <= self._last_frame_ts:
            return None
        self._last_frame_ts = frame.timestamp
        return frame

    def _ready(self) -> None:
        trigger = self._bundle.job.acquisition.trigger  # type: ignore[union-attr]
        mode = trigger.type
        if self._trigger_requested:
            self._begin_inspection()
            return
        if mode == "continuous":
            interval_s = trigger.continuous.interval_ms / 1000  # type: ignore[union-attr]
            if self._clock() - self._began_at >= interval_s and self._new_frame() is not None:
                self._begin_inspection()
            return
        if mode != "image_presence" or self._detector is None:
            return
        frame = self._new_frame()
        if frame is not None and self._detector.update(frame.image, frame.timestamp).present:
            self._go(State.WAITING_STILL)

    def _waiting_still(self) -> None:
        if self._trigger_requested:
            self._begin_inspection()
            return
        frame = self._new_frame()
        if frame is None or self._detector is None:
            return
        presence = self._detector.update(frame.image, frame.timestamp)
        if not presence.present:
            self._go(State.READY)  # the object left before it was still
        elif presence.still_for_s * 1000 >= self._bundle.job.acquisition.trigger.image_presence.still_ms:  # type: ignore[union-attr]
            self._begin_inspection()

    def _begin_inspection(self) -> None:
        # a pending reference goes with the inspection that starts now, whatever started it
        self._reference, self._trigger_reference = self._trigger_reference, ""
        pending, self._pending_trigger = self._pending_trigger, None
        source = pending if pending is not None and self._trigger_requested else TriggerInfo("image")
        self._trigger = replace(source, at=self._wall())
        self._trigger_requested = False
        with self._trigger_lock:
            self._trigger_taken = False
        self._began_at = self._clock()
        # an external signal is followed by the delay the job asks for, then the picture is taken: the frame must come after
        # this moment (FR-TRG-6), the same rule that keeps a buffered frame out (FR-ACQ-6)
        external = self._bundle.job.acquisition.trigger  # type: ignore[union-attr]
        delay_s = external.external.delay_ms / 1000 if external.type == "external" and external.external and source.source != "image" else 0.0
        self._t0 = self._began_at + delay_s
        self._go(State.INSPECTING)

    def _inspecting(self) -> None:
        frame = self._acq.frame_after(self._t0)  # captured after the trigger, never a buffered one (FR-ACQ-6)
        if frame is None:
            if self._clock() - self._t0 > self._inspect_timeout_s:
                self._finish(self._error(ErrorCode.NO_FRESH_FRAME), None)
            return
        started = self._clock()
        try:
            result = self._inspect(self._bundle, frame)  # type: ignore[arg-type]
        except Exception as exc:
            result = self._error(ErrorCode.INTERNAL, tr("Erro interno na inspeção ({kind})", kind=type(exc).__name__))
        if not isinstance(result, InspectionResult) or result.outcome not in tuple(Outcome):
            result = self._error(ErrorCode.INTERNAL, tr("Resultado de inspeção inválido"))
        elif self._acq.stalled():
            result = self._error(ErrorCode.CAMERA_LOST, tr("Câmera perdida durante a inspeção"))  # never a PASS after doubt
        elif result.outcome is Outcome.PASS and frame.timestamp <= self._t0:
            result = self._error(ErrorCode.NO_FRESH_FRAME, tr("Imagem anterior ao gatilho"))
        self._finish(result, frame, started)

    def _showing_result(self) -> None:
        mode = self._bundle.job.acquisition.trigger.type  # type: ignore[union-attr]
        if mode == "continuous":
            self._go(State.READY)
            return
        if self._detector is not None:
            frame = self._new_frame()
            if frame is not None and self._detector.update(frame.image, frame.timestamp).absent_for_s >= self._absent_s:
                self._go(State.READY)  # the object is gone: re-armed (FR-TRG-4)
            return
        if self._clock() - self._shown_at >= self._hold_s:
            self._go(State.READY)

    # --- camera lost --------------------------------------------------------------

    def _camera_lost(self) -> None:
        if self._state is State.INSPECTING:
            self._finish(self._error(ErrorCode.CAMERA_LOST), None)
        self._detail = self._acq.last_error or ""
        self._go(State.CAMERA_LOST)

    def _camera_lost_wait(self) -> None:
        if not self._acq.stalled() and self._acq.latest() is not None:
            # the acquisition re-applied the settings when it reconnected; they are checked again
            # before the next inspection (UC-09)
            self._detail = ""
            self._go(State.PREPARING)

    # --- results ------------------------------------------------------------------

    def _error(self, code: ErrorCode, reason: str | None = None) -> InspectionResult:
        return InspectionResult(outcome=Outcome.ERROR, reason=CATALOG[code].text if reason is None else reason, error_code=int(code))

    def _finish(self, result: InspectionResult, frame: Frame | None, started: float | None = None) -> None:
        if started is not None and result.duration_s == 0.0:
            result = replace(result, duration_s=self._clock() - started)
        if result.outcome is Outcome.ERROR and not result.error_code:
            result = replace(result, error_code=int(ErrorCode.INTERNAL))  # an inspector without codes: never an ERROR without one
        now, wall = self._clock(), self._wall()
        result = replace(
            result,
            sequence=self._sequence,
            job=self._job_ref,
            trigger=self._trigger,
            acquired_at=None if frame is None else wall - (now - frame.timestamp),
            decided_at=wall,
            simulated=bool(self._acq.simulated),
        )
        if self._save_sequence is not None:
            try:
                self._save_sequence(result.sequence)
            except Exception:  # a store that fails must not stop the station; the record of the result says it
                log.exception("could not save the sequence number")
        self._sequence = (self._sequence + 1) % 2**32
        self._trigger = None
        self._last_result = result
        self._shown_at = self._clock()
        job = self._bundle.job.job if self._bundle else None
        self._emit(
            StationEvent(
                "result",
                self._state,
                result=result,
                frame=frame,
                message=result.reason,
                job_id=str(job.id) if job else "",
                job_name=job.name if job else "",
                job_version=job.version if job else 0,
                reference=self._reference,
            )
        )
        self._reference = ""
        if self._state is State.INSPECTING:
            self._go(State.SHOWING_RESULT)

    def _go(self, new: State) -> None:
        previous, self._state = self._state, new
        if previous is not new:
            self._showing = self.showing_result
            self._emit(StationEvent("state", new, previous=previous, message=self._message(), showing_result=self._showing))

    def _emit(self, event: StationEvent) -> None:
        if self._on_event is None:
            return
        try:
            self._on_event(event)
        except Exception:  # a recorder or screen that fails must not stop the station
            log.exception("event handler failed")
