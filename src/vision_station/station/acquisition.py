"""Keeps the camera open and holds the newest frame (architecture §3, §7.4).

The thread (or `step()` in tests) reads frames as fast as they come, keeps only the latest, applies
the job's camera settings on every (re)connect, and retries a lost camera with growing delays.
After each apply the frames of the settling time are dropped: a camera may send a few frames with
other settings first (the C920 reopens its capture and sends overexposed frames), and the controller
must not take one of them as the empty scene or inspect it (VIA-0045).
A camera that sends only perfectly uniform frames for `dead_after_s` is lost too: an unplugged C920 keeps
sending black frames through DirectShow with no error (VIA-0050). A real camera always has some noise.
The station controller asks for a frame captured *after* a given moment, never one buffered
before it (FR-ACQ-6).
"""

import threading
import time
from collections.abc import Callable, Iterator, Mapping
from typing import Any

import numpy as np

from vision_station.cameras import ApplyReport, Camera, CameraError, Frame
from vision_station.cameras.orientation import orient
from vision_station.jobs import CameraProfile


class Acquisition:
    def __init__(
        self,
        camera: Camera,
        connection: Mapping[str, Any],
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        stall_timeout_s: float = 3.0,
        retry_delays_s: tuple[float, ...] = (1.0, 2.0, 5.0, 10.0),
        settle_s: float = 0.0,
        dead_after_s: float = 0.0,
    ):
        self._camera = camera
        self._connection = dict(connection)
        self.settle_s = settle_s  # frames are dropped for this long after each apply
        self.dead_after_s = dead_after_s  # only uniform frames for this long = lost (0: never)
        self._clock = clock
        self._sleep = sleep
        self.stall_timeout_s = stall_timeout_s
        self._retry_delays = retry_delays_s

        self._lock = threading.Lock()
        self._frames: Iterator[Frame] | None = None
        self._latest: Frame | None = None
        self._profile: CameraProfile | None = None
        self._raw: Mapping[str, bytes] | None = None
        self.profile_serial = 0  # counts configure() calls
        self.applied_serial = -1  # the profile_serial that was last applied successfully written
        self._settling: int | None = None  # the profile_serial just written, until the settling time is over
        self._settle_until = 0.0
        self._uniform_since: float | None = None
        self._reapply = False
        self._connected = False
        self._next_try = 0.0
        self._failures = 0
        self.generation = 0  # counts connections
        self.simulated = False  # the camera says its pictures are not the real station (Capabilities.simulated)
        self.last_apply: ApplyReport | None = None
        self.last_error: str | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    # --- state for the controller -------------------------------------------

    @property
    def connected(self) -> bool:
        return self._connected

    def latest(self) -> Frame | None:
        with self._lock:
            return self._latest

    def frame_after(self, t0: float) -> Frame | None:
        """The newest frame, only if it was captured after t0."""
        frame = self.latest()
        return frame if frame is not None and frame.timestamp > t0 else None

    def age_s(self) -> float | None:
        frame = self.latest()
        return None if frame is None else self._clock() - frame.timestamp

    def stalled(self) -> bool:
        """Not connected, or connected but no new frame for longer than the timeout."""
        if not self._connected:
            return True
        age = self.age_s()
        return age is not None and age > self.stall_timeout_s

    def exposure_us(self) -> float | None:
        """The exposure the camera says it is using now; None when it cannot say (or is not manual). A camera with
        coarse steps applies the nearest one, and this is how a search learns which."""
        if not self._connected:
            return None
        try:
            back = self._camera.read_back().get("exposure")
        except Exception:
            return None
        if isinstance(back, dict) and back.get("mode") == "manual" and back.get("value_us"):
            return float(back["value_us"])
        return None

    # --- configuration ------------------------------------------------------

    @property
    def profile(self) -> CameraProfile | None:
        """The camera profile in use (the active job's, or one being tuned)."""
        with self._lock:
            return self._profile

    @property
    def applied(self) -> bool:
        """The profile in use has been written to the camera since it was set."""
        return self.applied_serial == self.profile_serial

    def configure(self, profile: CameraProfile, raw: Mapping[str, bytes] | None = None) -> None:
        """Use this camera profile from now on: applied at once if connected, and on every reconnect."""
        with self._lock:
            self._profile, self._raw = profile, raw
            self.profile_serial += 1
            self._reapply = True

    # --- the work -----------------------------------------------------------

    def step(self) -> None:
        """One unit of work: connect if needed, apply settings if asked, read one frame."""
        if not self._connected:
            if self._clock() < self._next_try:
                return
            try:
                self._connect()
            except Exception as exc:  # any driver failure means: lost, retry later
                self._lose(exc)
                return
        if self._reapply:
            try:
                self._apply()
            except Exception as exc:
                self._lose(exc)
                return
        try:
            frame = next(self._frames)  # type: ignore[arg-type]
        except StopIteration:
            self._lose(CameraError("camera stream ended"))
            return
        except Exception as exc:
            self._lose(exc)
            return
        self._failures = 0
        if self.dead_after_s > 0 and self._dead(frame):
            self._lose(CameraError(f"a câmera só manda imagem uniforme (preta) há {self.dead_after_s:g} s: desconectada?"))
            return
        if self._settling is not None:
            if self._clock() < self._settle_until:
                return  # still settling: this frame may not show the new settings yet
            self.applied_serial, self._settling = self._settling, None
        with self._lock:
            if self._profile is not None and self._profile.orientation != "normal":
                frame = Frame(orient(frame.image, self._profile.orientation), frame.timestamp)  # FR-ACQ-10
            self._latest = frame

    def _dead(self, frame: Frame) -> bool:
        sample = np.asarray(frame.image)[::8, ::8]
        if sample.size and int(sample.max()) != int(sample.min()):
            self._uniform_since = None
            return False
        now = self._clock()
        if self._uniform_since is None:
            self._uniform_since = now
        return now - self._uniform_since >= self.dead_after_s

    def _connect(self) -> None:
        self._camera.open(self._connection)
        self.simulated = bool(self._camera.capabilities().simulated)
        self._frames = self._camera.frames()
        self._connected = True
        self.generation += 1
        self.last_error = None
        self._reapply = self._profile is not None  # settings are written on every connect (FR-ACQ-4/5)

    def _apply(self) -> None:
        with self._lock:
            profile, raw, serial = self._profile, self._raw, self.profile_serial
            self._reapply = False
            self._latest = None  # taken with the settings from before
        if profile is None:
            return
        self.last_apply = self._camera.apply(profile, raw)
        self._settling, self._settle_until = serial, self._clock() + self.settle_s

    def _lose(self, exc: BaseException) -> None:
        try:
            self._camera.close()
        except Exception:
            pass
        with self._lock:
            self._latest = None  # a frame from before the loss must never be used
        self._settling = None  # written again on the reconnect
        self._uniform_since = None
        self._connected = False
        self._frames = None
        self.last_error = f"{type(exc).__name__}: {exc}"
        delay = self._retry_delays[min(self._failures, len(self._retry_delays) - 1)]
        self._failures += 1
        self._next_try = self._clock() + delay

    # --- thread ---------------------------------------------------------------

    def start(self) -> None:
        if self._thread is not None:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="acquisition", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None
        try:
            self._camera.close()
        except Exception:
            pass
        self._connected = False

    def _run(self) -> None:
        while not self._stop.is_set():
            was_connected = self._connected
            self.step()
            if not self._connected or not was_connected:
                self._sleep(0.05)
