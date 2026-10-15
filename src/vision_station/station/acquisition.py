"""Keeps the camera open and holds the newest frame (architecture §3, §7.4).

The thread (or `step()` in tests) reads frames as fast as they come, keeps only the latest, applies
the job's camera settings on every (re)connect, and retries a lost camera with growing delays.
The station controller asks for a frame captured *after* a given moment, never one buffered
before it (FR-ACQ-6).
"""

import threading
import time
from collections.abc import Callable, Iterator, Mapping
from typing import Any

from vision_station.cameras import ApplyReport, Camera, CameraError, Frame
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
    ):
        self._camera = camera
        self._connection = dict(connection)
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
        self._reapply = False
        self._connected = False
        self._next_try = 0.0
        self._failures = 0
        self.generation = 0  # counts connections
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
        with self._lock:
            self._latest = frame
        self._failures = 0

    def _connect(self) -> None:
        self._camera.open(self._connection)
        self._frames = self._camera.frames()
        self._connected = True
        self.generation += 1
        self.last_error = None
        self._reapply = self._profile is not None  # settings are written on every connect (FR-ACQ-4/5)

    def _apply(self) -> None:
        with self._lock:
            profile, raw, serial = self._profile, self._raw, self.profile_serial
            self._reapply = False
        if profile is None:
            return
        self.last_apply = self._camera.apply(profile, raw)
        self.applied_serial = serial

    def _lose(self, exc: BaseException) -> None:
        try:
            self._camera.close()
        except Exception:
            pass
        with self._lock:
            self._latest = None  # a frame from before the loss must never be used
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
