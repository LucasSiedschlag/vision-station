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
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from vision_station.cameras import Frame, SettingStatus
from vision_station.results import InspectionResult, Outcome
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


# What the operator screen shows (architecture §6). "waiting" can be replaced by the job (`ui.waiting`).
MESSAGES = {
    State.STARTING: "Preparando…",
    State.PREPARING: "Preparando…",
    State.READY: "Aguardando objeto",
    State.WAITING_STILL: "Aguardando objeto",
    State.INSPECTING: "Inspecionando…",
    State.CAMERA_LOST: "Câmera desconectada",
    State.FAULT: "Falha na verificação — chamar manutenção",
    State.PAUSED: "Em manutenção",
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
        return VerifyResult(False, "ajustes da câmera não aplicados")
    rejected = sorted(k for k, s in report.status.items() if s is SettingStatus.REJECTED)
    if rejected:
        return VerifyResult(False, "ajuste não aplicado: " + ", ".join(rejected))
    unsupported = tuple(sorted(f"{k}: {report.detail.get(k, 'não suportado')}" for k, s in report.status.items() if s is SettingStatus.NOT_SUPPORTED))
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


@dataclass
class _Command:
    name: str
    bundle: JobBundle | None = None


@dataclass
class Status:
    state: State
    message: str
    detail: str = ""
    job_name: str = ""
    job_version: int = 0
    last_result: InspectionResult | None = None
    warnings: tuple[str, ...] = field(default_factory=tuple)


class StationController:
    def __init__(
        self,
        acquisition: Acquisition,
        inspect: Inspector,
        verifier: Verifier = basic_verifier,
        clock: Callable[[], float] = time.monotonic,
        on_event: Callable[[StationEvent], Any] | None = None,
        hold_s: float = 2.0,
        absent_s: float = 0.3,
        inspect_timeout_s: float = 5.0,
    ):
        self._acq = acquisition
        self._inspect = inspect
        self._verify = verifier
        self._clock = clock
        self._on_event = on_event
        self._hold_s = hold_s
        self._absent_s = absent_s
        self._inspect_timeout_s = inspect_timeout_s

        self._commands: queue.Queue[_Command] = queue.Queue()
        self._bundle: JobBundle | None = None
        self._detector: PresenceDetector | None = None
        self._state = State.STARTING
        self._detail = ""
        self._warnings: tuple[str, ...] = ()
        self._last_result: InspectionResult | None = None
        self._trigger_requested = False
        self._t0 = 0.0  # when the current inspection was triggered
        self._shown_at = 0.0
        self._last_frame_ts = -1.0
        self._stop = threading.Event()

    # --- commands (safe to call from other threads) ------------------------------

    def start(self, bundle: JobBundle) -> None:
        self._commands.put(_Command("load", bundle))

    def switch_job(self, bundle: JobBundle) -> None:
        self._commands.put(_Command("load", bundle))

    def request_trigger(self) -> None:
        """Manual or external trigger (FR-TRG-2/3)."""
        self._commands.put(_Command("trigger"))

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

    def status(self) -> Status:
        job = self._bundle.job.job if self._bundle else None
        return Status(
            state=self._state,
            message=self._message(),
            detail=self._detail,
            job_name=job.name if job else "",
            job_version=job.version if job else 0,
            last_result=self._last_result,
            warnings=self._warnings,
        )

    def _message(self) -> str:
        if self._state is State.SHOWING_RESULT and self._last_result is not None:
            r = self._last_result
            return f"{r.outcome}: {r.reason}" if r.reason else str(r.outcome)
        if self._state in (State.READY, State.WAITING_STILL) and self._bundle and self._bundle.job.ui.waiting:
            return self._bundle.job.ui.waiting
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

    # --- commands -------------------------------------------------------------------

    def _apply_command(self, command: _Command) -> None:
        if command.name == "load" and command.bundle is not None:
            self._load(command.bundle)
        elif command.name == "trigger":
            self._trigger_requested = True
        elif command.name == "pause" and self._state in (State.READY, State.WAITING_STILL, State.SHOWING_RESULT):
            self._go(State.PAUSED)
        elif command.name == "resume" and self._state is State.PAUSED:
            self._prepare()
        elif command.name == "retry" and self._state is State.FAULT:
            self._prepare()
        elif command.name == "reset_background" and self._detector is not None:
            self._detector.reset_background()

    def _load(self, bundle: JobBundle) -> None:
        if self._state is State.INSPECTING:
            self._finish(self._error("Troca de job durante a inspeção"), None)
        self._bundle = bundle
        trigger = bundle.job.trigger
        self._detector = PresenceDetector(trigger) if trigger.presence_roi is not None else None
        self._prepare()

    def _prepare(self) -> None:
        assert self._bundle is not None
        self._trigger_requested = False
        self._acq.configure(self._bundle.profile)
        self._detail = ""
        self._go(State.PREPARING)

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
        mode = self._bundle.job.trigger.mode  # type: ignore[union-attr]
        if self._trigger_requested:
            self._begin_inspection()
            return
        if mode == "continuous":
            if self._new_frame() is not None:
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
        elif presence.still_for_s * 1000 >= self._bundle.job.trigger.still_ms:  # type: ignore[union-attr,operator]
            self._begin_inspection()

    def _begin_inspection(self) -> None:
        self._trigger_requested = False
        self._t0 = self._clock()
        self._go(State.INSPECTING)

    def _inspecting(self) -> None:
        frame = self._acq.frame_after(self._t0)  # captured after the trigger, never a buffered one (FR-ACQ-6)
        if frame is None:
            if self._clock() - self._t0 > self._inspect_timeout_s:
                self._finish(self._error("Imagem não recebida da câmera"), None)
            return
        started = self._clock()
        try:
            result = self._inspect(self._bundle, frame)  # type: ignore[arg-type]
        except Exception as exc:
            result = self._error(f"Erro interno na inspeção ({type(exc).__name__})")
        if not isinstance(result, InspectionResult) or result.outcome not in tuple(Outcome):
            result = self._error("Resultado de inspeção inválido")
        elif self._acq.stalled():
            result = self._error("Câmera perdida durante a inspeção")  # never a PASS after doubt
        elif result.outcome is Outcome.PASS and frame.timestamp <= self._t0:
            result = self._error("Imagem anterior ao gatilho")
        self._finish(result, frame, started)

    def _showing_result(self) -> None:
        mode = self._bundle.job.trigger.mode  # type: ignore[union-attr]
        if mode == "continuous":
            self._go(State.READY)
            return
        if self._detector is not None and self._bundle.job.trigger.presence_roi is not None:  # type: ignore[union-attr]
            frame = self._new_frame()
            if frame is not None and self._detector.update(frame.image, frame.timestamp).absent_for_s >= self._absent_s:
                self._go(State.READY)  # the object is gone: re-armed (FR-TRG-4)
            return
        if self._clock() - self._shown_at >= self._hold_s:
            self._go(State.READY)

    # --- camera lost --------------------------------------------------------------

    def _camera_lost(self) -> None:
        if self._state is State.INSPECTING:
            self._finish(self._error("Câmera desconectada durante a inspeção"), None)
        self._detail = self._acq.last_error or ""
        self._go(State.CAMERA_LOST)

    def _camera_lost_wait(self) -> None:
        if not self._acq.stalled() and self._acq.latest() is not None:
            # the acquisition re-applied the settings when it reconnected; they are checked again
            # before the next inspection (UC-09)
            self._detail = ""
            self._go(State.PREPARING)

    # --- results ------------------------------------------------------------------

    def _error(self, reason: str) -> InspectionResult:
        return InspectionResult(outcome=Outcome.ERROR, reason=reason)

    def _finish(self, result: InspectionResult, frame: Frame | None, started: float | None = None) -> None:
        if started is not None and result.duration_s == 0.0:
            result = InspectionResult(result.outcome, result.reason, result.scores, result.details, self._clock() - started)
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
            )
        )
        if self._state is State.INSPECTING:
            self._go(State.SHOWING_RESULT)

    def _go(self, new: State) -> None:
        previous, self._state = self._state, new
        if previous is not new:
            self._emit(StationEvent("state", new, previous=previous, message=self._message()))

    def _emit(self, event: StationEvent) -> None:
        if self._on_event is None:
            return
        try:
            self._on_event(event)
        except Exception:  # a recorder or screen that fails must not stop the station
            log.exception("event handler failed")
