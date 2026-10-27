"""Image-based trigger: is an object present in the area, and is it still? (FR-TRG-1, FR-TRG-4)

The area is compared with the empty scene (a slowly updated background) to tell presence, and with
the previous frame to tell motion. An object that stays is inspected once: the controller re-arms
only after the area has been empty again.
"""

from dataclasses import dataclass

import cv2
import numpy as np

from vision_station.jobs.job import PresenceTrigger

BACKGROUND_RATE = 0.05  # how fast the empty-scene background follows slow light changes
WORK_SIDE = 320  # at most this many pixels on the longer side of the picture the area is compared on (VIA-0108, NFR-PERF-7)


@dataclass(frozen=True)
class Presence:
    present: bool
    moving: bool
    still_for_s: float  # how long the object has been present and not moving
    absent_for_s: float  # how long the area has been empty


class PresenceDetector:
    def __init__(self, trigger: PresenceTrigger):
        self._roi = trigger.roi
        self._diff = trigger.diff_threshold
        self._min_area = trigger.min_area
        self._motion_area = trigger.motion_area
        self._background: np.ndarray | None = None
        self._previous: np.ndarray | None = None
        self._still_since: float | None = None
        self._absent_since: float | None = None
        self._present = False

    def reset_background(self) -> None:
        """Forget the empty scene; the next frame is taken as empty."""
        self._background = None
        self._previous = None
        self._still_since = None
        self._absent_since = None
        self._present = False

    def _crop(self, image: np.ndarray) -> np.ndarray:
        """The area as a small gray picture: the comparison costs what the pixels cost, and it runs on every frame while
        the station waits. The areas are fractions of the region and the threshold is a gray level, so shrinking it (by the
        mean of the pixels it covers, which also smooths the noise) keeps what is decided (VIA-0108)."""
        h, w = image.shape[:2]
        x0, y0, x1, y1 = self._roi
        region = image[int(y0 * h) : max(int(y1 * h), int(y0 * h) + 1), int(x0 * w) : max(int(x1 * w), int(x0 * w) + 1)]
        k = -(-max(region.shape[:2]) // WORK_SIDE)  # a whole number of pixels per working pixel: OpenCV's fast path for the mean
        if k > 1:  # a region already small is not enlarged
            rows, cols = region.shape[0] // k, region.shape[1] // k
            region = cv2.resize(region[: rows * k, : cols * k], (cols, rows), interpolation=cv2.INTER_AREA)
        gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY) if region.ndim == 3 else region
        return cv2.GaussianBlur(gray, (3, 3), 0).astype(np.float32)

    def update(self, image: np.ndarray, t: float) -> Presence:
        roi = self._crop(image)
        if self._background is None:
            self._background = roi.copy()
        present_area = float((np.abs(roi - self._background) > self._diff).mean())
        moving_area = float((np.abs(roi - self._previous) > self._diff).mean()) if self._previous is not None else 0.0
        self._previous = roi

        present = present_area >= self._min_area
        moving = moving_area >= self._motion_area
        if not present:
            cv2.accumulateWeighted(roi, self._background, BACKGROUND_RATE)  # follow slow light changes
        if present != self._present or self._absent_since is None:
            self._absent_since = None if present else t
        self._present = present
        if present and not moving:
            if self._still_since is None:
                self._still_since = t
        else:
            self._still_since = None
        return Presence(
            present=present,
            moving=moving,
            still_for_s=0.0 if self._still_since is None else t - self._still_since,
            absent_for_s=0.0 if self._absent_since is None else t - self._absent_since,
        )
