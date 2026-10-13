"""UVC camera driver for the Logitech C920 (TD-04, architecture §5.3).

The logic here is OS-independent: frames come from an OpenCV-like capture and
the camera controls from a `Controls` object. On Windows these are DirectShow
and duvc-ctl (`duvc_backend.py`); tests use fakes.

Known C920 behavior this driver works around:
- the firmware ignores manual values while the matching auto mode is on, so
  `apply` works in two passes: every control to manual (keeping its current
  value), wait, then write the values;
- values can reset after a replug or restart, so the station controller calls
  `apply` again on every open, reconnect and job activation;
- some writes are silently ignored, so every value is read back and compared.
"""

import math
import time
from collections import deque
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from typing import Any, Protocol

import cv2
import numpy as np

from vision_station.cameras.base import (
    ApplyReport,
    Camera,
    CameraError,
    Capabilities,
    Frame,
    Health,
    SettingStatus,
)
from vision_station.jobs import CameraProfile

FOURCC = {"mjpeg": "MJPG", "yuyv": "YUY2"}
POWER_LINE_VALUE = {50: 1, 60: 2}  # UVC power line frequency: 0 off, 1 = 50 Hz, 2 = 60 Hz
SETTLE_S = 0.2  # TD-04: wait between switching to manual and writing values
MAX_READ_FAILURES = 5


class ControlError(Exception):
    """A control is missing on this unit, or the write was refused."""


@dataclass(frozen=True)
class ControlRange:
    min: int
    max: int
    step: int = 1

    def contains(self, value: int) -> bool:
        return self.min <= value <= self.max

    def align(self, value: int) -> int:
        if self.step <= 1:
            return value
        return self.min + round((value - self.min) / self.step) * self.step


class Controls(Protocol):
    """UVC controls by name: exposure, gain, white_balance, focus, zoom, power_line_frequency."""

    def range(self, name: str) -> ControlRange | None:
        """None when this unit does not have the control."""

    def get(self, name: str) -> tuple[int, bool]:
        """(value, is_auto). Raises ControlError if the control cannot be read."""

    def set(self, name: str, value: int, auto: bool) -> None:
        """Raises ControlError if the write is refused."""

    def close(self) -> None: ...


class Capture(Protocol):
    """The part of cv2.VideoCapture this driver uses."""

    def isOpened(self) -> bool: ...  # noqa: N802
    def set(self, prop: int, value: float) -> bool: ...
    def get(self, prop: int) -> float: ...
    def read(self) -> tuple[bool, np.ndarray | None]: ...
    def release(self) -> None: ...


# connection -> (controls, device index for the capture)
ControlsFactory = Callable[[Mapping[str, Any]], tuple[Controls, int]]
CaptureFactory = Callable[[int, list[int] | None], Capture]


def open_directshow_capture(index: int, params: list[int] | None = None) -> Capture:
    """`params` is a flat [prop, value, ...] list applied while opening (OpenCV 4.5.2+)."""
    if params:
        return cv2.VideoCapture(index, cv2.CAP_DSHOW, params)
    return cv2.VideoCapture(index, cv2.CAP_DSHOW)


def exposure_us_to_raw(us: float, rng: ControlRange) -> int:
    """DirectShow exposure is log2(seconds) (C920: about -11 to -2).

    A unit that reports a positive range uses 100 us steps instead.
    """
    if rng.min >= 0:
        return round(us / 100)
    return round(math.log2(us / 1e6))


def exposure_raw_to_us(raw: int, rng: ControlRange) -> float:
    if rng.min >= 0:
        return raw * 100.0
    return (2.0**raw) * 1e6


class UvcCamera(Camera):
    """connection: {"device_path" | "device_name" | "device_index": ...}, resolved by the controls factory."""

    def __init__(
        self,
        controls_factory: ControlsFactory,
        capture_factory: CaptureFactory = open_directshow_capture,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self._controls_factory = controls_factory
        self._capture_factory = capture_factory
        self._clock = clock
        self._sleep = sleep
        self._controls: Controls | None = None
        self._index = 0
        self._capture: Capture | None = None
        self._stamps: deque[float] = deque(maxlen=30)
        self._ranges: dict[str, ControlRange] = {}
        self.open_strategy = ""  # how the capture was last opened, for diagnostics

    # --- lifecycle -----------------------------------------------------------

    def open(self, connection: Mapping[str, Any]) -> None:
        self.close()
        self._controls, self._index = self._controls_factory(connection)
        names = ("exposure", "gain", "white_balance", "focus", "zoom", "power_line_frequency")
        self._ranges = {n: r for n in names if (r := self._controls.range(n)) is not None}
        self._open_capture(fourcc=FOURCC["mjpeg"], size=None)
        self._stamps.clear()

    def close(self) -> None:
        if self._capture is not None:
            self._capture.release()
            self._capture = None
        if self._controls is not None:
            self._controls.close()
            self._controls = None

    def capabilities(self) -> Capabilities:
        self._require_open()
        names = {"resolution", "pixel_format"}
        for name in self._ranges:
            names.add("power_line_hz" if name == "power_line_frequency" else name)
        return Capabilities(settings=frozenset(names), readable=frozenset(names), has_snapshot=False)

    # --- settings ------------------------------------------------------------

    def apply(self, profile: CameraProfile, raw: Mapping[str, bytes] | None = None) -> ApplyReport:
        self._require_open()
        status: dict[str, SettingStatus] = {}
        detail: dict[str, str] = {}

        def done(name: str, st: SettingStatus, why: str = "") -> None:
            status[name] = st
            if why:
                detail[name] = why

        self._apply_format(profile, done)

        # Targets: name -> (control, desired raw value or None for auto, note)
        targets: dict[str, tuple[str, int | None, str]] = {}
        self._plan(profile, targets, done)

        # Pass 1: every control to manual (or auto), keeping the value it has now
        for setting, (control, wanted, _) in targets.items():
            try:
                current, _ = self._controls.get(control)  # type: ignore[union-attr]
                self._controls.set(control, current, auto=wanted is None)  # type: ignore[union-attr]
            except ControlError as exc:
                done(setting, SettingStatus.REJECTED, f"cannot switch mode: {exc}")
        self._sleep(SETTLE_S)

        # Pass 2: write the values, then read each one back
        for setting, (control, wanted, note) in targets.items():
            if setting in status:
                continue
            try:
                if wanted is not None:
                    self._controls.set(control, wanted, auto=False)  # type: ignore[union-attr]
                value, is_auto = self._controls.get(control)  # type: ignore[union-attr]
            except ControlError as exc:
                done(setting, SettingStatus.REJECTED, str(exc))
                continue
            if wanted is None:
                ok = is_auto
            else:
                ok = (not is_auto) and value == wanted
            if ok:
                done(setting, SettingStatus.APPLIED, note)
            else:
                shown = "auto" if is_auto else str(value)
                done(setting, SettingStatus.REJECTED, f"camera kept {shown}, wanted {wanted if wanted is not None else 'auto'}")
        return ApplyReport(status=status, detail=detail)

    def read_back(self) -> dict[str, Any]:
        self._require_open()
        out: dict[str, Any] = {}
        if self._capture is not None:
            w = int(self._capture.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(self._capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
            out["resolution"] = (w, h)
            code = int(self._capture.get(cv2.CAP_PROP_FOURCC))
            text = "".join(chr((code >> (8 * i)) & 0xFF) for i in range(4))
            for name, fourcc in FOURCC.items():
                if text == fourcc:
                    out["pixel_format"] = name

        def read(control: str) -> tuple[int, bool] | None:
            if control not in self._ranges:
                return None
            try:
                return self._controls.get(control)  # type: ignore[union-attr]
            except ControlError:
                return None

        if (r := read("exposure")) is not None:
            out["exposure"] = (
                {"mode": "auto"}
                if r[1]
                else {"mode": "manual", "value_us": exposure_raw_to_us(r[0], self._ranges["exposure"])}
            )
        for setting in ("gain", "focus"):
            if (r := read(setting)) is not None:
                out[setting] = {"mode": "auto"} if r[1] else {"mode": "manual", "value": float(r[0])}
        if (r := read("white_balance")) is not None:
            out["white_balance"] = {"mode": "auto"} if r[1] else {"mode": "manual", "kelvin": r[0]}
        if (r := read("zoom")) is not None:
            out["zoom"] = {"value": float(r[0])}
        if (r := read("power_line_frequency")) is not None:
            hz = {v: k for k, v in POWER_LINE_VALUE.items()}.get(r[0])
            if hz is not None:
                out["power_line_hz"] = hz
        return out

    # --- frames --------------------------------------------------------------

    def frames(self) -> Iterator[Frame]:
        self._require_open()
        failures = 0
        while self._capture is not None:
            ok, image = self._capture.read()
            if not ok or image is None:
                failures += 1
                if failures >= MAX_READ_FAILURES:
                    raise CameraError("camera stopped delivering frames")
                continue
            failures = 0
            stamp = self._clock()
            self._stamps.append(stamp)
            yield Frame(image=image, timestamp=stamp)

    def snapshot(self) -> Frame | None:
        return None  # the C920 has no separate still mode

    def health(self) -> Health:
        age = self._clock() - self._stamps[-1] if self._stamps else None
        fps = 0.0
        if len(self._stamps) > 1 and self._stamps[-1] > self._stamps[0]:
            fps = (len(self._stamps) - 1) / (self._stamps[-1] - self._stamps[0])
        connected = self._capture is not None and self._capture.isOpened()
        return Health(connected=connected, fps=fps, last_frame_age_s=age)

    # --- internals -----------------------------------------------------------

    def _open_capture(self, fourcc: str, size: tuple[int, int] | None) -> None:
        """Open through DirectShow and get the wanted format.

        With DirectShow the order of the settings decides whether the format sticks (the C920
        stays on YUY2, about 5 fps at 1080p, if it does not), and what works depends on the
        OpenCV build. So the ways of asking are tried in turn, each checked by reading the
        format back, and the first that works is kept (`open_strategy` says which).
        """
        if self._capture is not None:
            self._capture.release()
            self._capture = None
        code = cv2.VideoWriter.fourcc(*fourcc)
        width, height = size if size is not None else (None, None)
        P = cv2

        def with_params() -> Capture:
            params = [P.CAP_PROP_FOURCC, code]
            if size is not None:
                params += [P.CAP_PROP_FRAME_WIDTH, width, P.CAP_PROP_FRAME_HEIGHT, height]
            return self._capture_factory(self._index, params)

        def fourcc_first() -> Capture:
            cap = self._capture_factory(self._index, None)
            cap.set(P.CAP_PROP_FOURCC, code)
            if size is not None:
                cap.set(P.CAP_PROP_FRAME_WIDTH, width)
                cap.set(P.CAP_PROP_FRAME_HEIGHT, height)
            return cap

        def size_first() -> Capture:
            cap = self._capture_factory(self._index, None)
            if size is not None:
                cap.set(P.CAP_PROP_FRAME_WIDTH, width)
                cap.set(P.CAP_PROP_FRAME_HEIGHT, height)
            cap.set(P.CAP_PROP_FOURCC, code)
            if size is not None:  # some builds restart the graph when the format changes
                cap.set(P.CAP_PROP_FRAME_WIDTH, width)
                cap.set(P.CAP_PROP_FRAME_HEIGHT, height)
            return cap

        best: Capture | None = None
        for name, attempt in (("params", with_params), ("fourcc-first", fourcc_first), ("size-first", size_first)):
            cap = attempt()
            if not cap.isOpened():
                cap.release()
                raise CameraError(f"cannot open camera {self._index} (is another program using it?)")
            cap.set(P.CAP_PROP_BUFFERSIZE, 1)
            if best is not None:
                best.release()
            best = cap
            self.open_strategy = name
            if self._format_matches(cap, code, size):
                break
        self._capture = best

    @staticmethod
    def _format_matches(cap: Capture, code: int, size: tuple[int, int] | None) -> bool:
        if int(cap.get(cv2.CAP_PROP_FOURCC)) != code:
            return False
        if size is None:
            return True
        return (int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))) == tuple(size)

    def _apply_format(self, profile: CameraProfile, done: Callable[..., None]) -> None:
        fourcc = FOURCC[profile.pixel_format or "mjpeg"]
        self._open_capture(fourcc=fourcc, size=profile.resolution)
        got = self.read_back()
        want_fmt = profile.pixel_format or "mjpeg"
        if got.get("pixel_format") == want_fmt:
            done("pixel_format", SettingStatus.APPLIED)
        else:
            done("pixel_format", SettingStatus.REJECTED, f"camera uses {got.get('pixel_format')}, wanted {want_fmt}")
        if got.get("resolution") == tuple(profile.resolution):
            done("resolution", SettingStatus.APPLIED)
        else:
            done("resolution", SettingStatus.REJECTED, f"camera uses {got.get('resolution')}, wanted {tuple(profile.resolution)}")

    def _plan(
        self,
        profile: CameraProfile,
        targets: dict[str, tuple[str, int | None, str]],
        done: Callable[..., None],
    ) -> None:
        """Work out the raw value for each setting; report the ones that cannot be applied."""

        def target(setting: str, control: str, raw_value: int | None, note: str = "") -> None:
            rng = self._ranges.get(control)
            if rng is None:
                done(setting, SettingStatus.NOT_SUPPORTED, f"camera has no {control}")
            elif raw_value is None:
                targets[setting] = (control, None, note)
            elif not rng.contains(raw_value):
                done(setting, SettingStatus.REJECTED, f"{raw_value} outside {rng.min}..{rng.max}")
            else:
                aligned = rng.align(raw_value)
                targets[setting] = (control, aligned, note)

        exp = profile.exposure
        if exp.mode == "auto":
            target("exposure", "exposure", None)
        elif (rng := self._ranges.get("exposure")) is None:
            done("exposure", SettingStatus.NOT_SUPPORTED, "camera has no exposure")
        else:
            raw_value = exposure_us_to_raw(exp.value_us, rng)  # type: ignore[arg-type]
            got_us = exposure_raw_to_us(raw_value, rng)
            note = f"{exp.value_us:g} us requested, nearest step is {got_us:.0f} us" if abs(got_us - exp.value_us) > 1 else ""  # type: ignore[operator]
            target("exposure", "exposure", raw_value, note)

        for setting in ("gain", "focus"):
            cfg = getattr(profile, setting)
            target(setting, setting, None if cfg.mode == "auto" else round(cfg.value))

        wb = profile.white_balance
        target("white_balance", "white_balance", None if wb.mode == "auto" else wb.kelvin)

        if profile.zoom is not None:
            target("zoom", "zoom", round(profile.zoom.value))

        target("power_line_hz", "power_line_frequency", POWER_LINE_VALUE[profile.power_line_hz])

        # Low light compensation (auto-exposure priority) only acts with auto exposure and
        # is not reachable through DirectShow: "off" holds with manual exposure, "on" cannot be set.
        if profile.low_light_compensation:
            done("low_light_compensation", SettingStatus.NOT_SUPPORTED, "cannot be enabled through DirectShow")
        elif profile.exposure.mode == "manual":
            done("low_light_compensation", SettingStatus.APPLIED, "off while exposure is manual")
        else:
            done("low_light_compensation", SettingStatus.NOT_SUPPORTED, "cannot be disabled with auto exposure")

    def _require_open(self) -> None:
        if self._controls is None:
            raise CameraError("camera is not open")
