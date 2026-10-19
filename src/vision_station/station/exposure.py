"""*Auto uma vez*: find the exposure once, then keep it (FR-ACQ-11, Cognex `AcquireImage` Auto Exposure single-shot).

The search writes an exposure to the camera, waits for the settings to take hold, measures how much of a region is
saturated, and narrows the range, as a bisection on the logarithm of the exposure: the saturated share only grows
when the exposure grows. It stops when the share is near the target or the range is as narrow as a camera can tell
apart (the C920 only has steps of a factor of two). The value it returns is fixed in the job, so the inspection
never depends on the light of the moment. It runs in the editor, with the station paused.
"""

import math
import time
from collections.abc import Callable
from dataclasses import dataclass

import cv2
import numpy as np

from vision_station.algorithms.metrics import SATURATED_FROM
from vision_station.core.i18n import tr
from vision_station.jobs import CameraProfile
from vision_station.jobs.camera_profile import AutoOnce, Exposure
from vision_station.station.acquisition import Acquisition

MIN_EXPOSURE_US = 100.0
TOLERANCE_PP = 1.0  # percentage points of saturated pixels that count as "at the target"
NARROW_RATIO = 1.03  # a range this narrow (3 %) is finer than any camera tells apart
STAGNANT_STOP = 2  # measures in a row that land on a step already measured: a coarse ladder, the search is over
FRAMES_PER_STEP = 2  # the median of these is the measure of a step


class ExposureError(Exception):
    """The camera did not answer the search (not connected, or the settings never took hold)."""


@dataclass(frozen=True)
class Measure:
    exposure_us: float
    saturated_percent: float


@dataclass(frozen=True)
class AutoExposure:
    value_us: float  # the exposure to keep
    saturated_percent: float  # what it gave
    target_percent: float
    reached: bool  # within the tolerance of the target; False: the best the range allowed
    limit: str  # "" | "max" (still short of the target at the maximum) | "min" (over the target at the minimum)
    steps: tuple[Measure, ...]


def saturated_percent(image: np.ndarray, region: tuple[float, float, float, float] | None) -> float:
    """The share, in percent, of the pixels of `region` (fractions of the frame; all of it when None) at the top."""
    height, width = image.shape[:2]
    if region is not None:
        x0, y0, x1, y1 = region
        image = image[int(y0 * height) : max(int(y1 * height), int(y0 * height) + 1), int(x0 * width) : max(int(x1 * width), int(x0 * width) + 1)]
    gray = image if image.ndim == 2 else cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return float((gray >= SATURATED_FROM).mean() * 100.0) if gray.size else 0.0


def measure_exposure(
    acquisition: Acquisition,
    profile: CameraProfile,
    pump: Callable[[], None] | None = None,
    clock: Callable[[], float] = time.monotonic,
    step_timeout_s: float = 8.0,
) -> AutoExposure:
    """Search the exposure of `profile` (its other settings stay as they are), leave the camera on the result.

    `pump` is called while waiting for the camera; the default sleeps a little (the acquisition thread does the
    work). A test passes a function that runs the acquisition by hand."""
    params = profile.exposure.auto_once or AutoOnce()
    wait = pump or (lambda: time.sleep(0.02))
    hi_limit = max(params.max_exposure_us, MIN_EXPOSURE_US * NARROW_RATIO)

    def use(exposure_us: float) -> None:
        exposure = Exposure(mode="manual", value_us=exposure_us, auto_once=params)
        acquisition.configure(profile.model_copy(update={"exposure": exposure}))

    def settled() -> None:
        """Wait until the settings are written and the first picture after them has come."""
        deadline = clock() + step_timeout_s
        while not (acquisition.applied and acquisition.latest() is not None):
            if clock() > deadline:
                raise ExposureError(tr("a câmera não está conectada") if not acquisition.connected else tr("a câmera não aplicou o ajuste a tempo"))
            wait()

    def measure(exposure_us: float) -> Measure:
        exposure_us = round(exposure_us, 1)  # what is written to the camera
        use(exposure_us)
        settled()
        shares: list[float] = []
        seen = -math.inf
        deadline = clock() + step_timeout_s
        while len(shares) < FRAMES_PER_STEP:
            frame = acquisition.latest()
            if frame is not None and frame.timestamp > seen:
                seen = frame.timestamp
                shares.append(saturated_percent(frame.image, params.region))
            elif clock() > deadline:
                raise ExposureError(tr("a câmera parou de mandar imagem"))
            else:
                wait()
        return Measure(acquisition.exposure_us() or exposure_us, float(np.median(shares)))  # the step the camera took

    steps: list[Measure] = []

    def take(exposure_us: float) -> Measure:
        m = measure(exposure_us)
        steps.append(m)
        return m

    target = params.target_brightness

    def closeness(m: Measure) -> tuple[float, float]:
        """Nearer the target first; between equals the longer exposure, which has more light and less noise."""
        return (round(abs(m.saturated_percent - target), 2), -m.exposure_us)

    def best_so_far() -> Measure:
        # a camera with coarse steps may take a longer one than asked for: the maximum is never gone over
        allowed = [s for s in steps if s.exposure_us <= params.max_exposure_us]
        return min(allowed or [min(steps, key=lambda s: s.exposure_us)], key=closeness)

    lo, hi = MIN_EXPOSURE_US, hi_limit
    limit = ""
    top = take(hi)
    probe = hi
    for _ in range(3):
        if top.exposure_us <= params.max_exposure_us:
            break
        probe /= 1.5  # the camera took a step longer than the maximum: look for one that is not
        take(probe)
    if top.saturated_percent <= target:
        limit = "max"  # even the longest exposure leaves the picture below the target
    else:
        bottom = take(lo)
        if bottom.saturated_percent >= target:
            limit = "min"  # even the shortest one is over it
        else:
            stagnant = 0
            while hi / lo > NARROW_RATIO and abs(best_so_far().saturated_percent - target) > TOLERANCE_PP and stagnant < STAGNANT_STOP:
                mid = math.sqrt(lo * hi)
                known = {s.exposure_us for s in steps}
                m = take(mid)
                stagnant = stagnant + 1 if m.exposure_us in known else 0
                if m.saturated_percent < target:
                    lo = mid
                else:
                    hi = mid
    best = best_so_far()
    use(best.exposure_us)  # leave the live view on what was chosen (a step the camera really has)
    settled()
    reached = not limit and abs(best.saturated_percent - target) <= TOLERANCE_PP
    return AutoExposure(round(best.exposure_us, 1), round(best.saturated_percent, 2), target, reached, limit, tuple(steps))
