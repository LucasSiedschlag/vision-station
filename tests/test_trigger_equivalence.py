"""The image trigger works on a reduced picture to spend little CPU while it waits (VIA-0108, NFR-PERF-7); it must
decide exactly what the full-resolution version decided. The old algorithm is kept here as the reference."""

import cv2
import numpy as np
import pytest

from vision_station.jobs.job import PresenceTrigger
from vision_station.station.trigger import BACKGROUND_RATE, PresenceDetector

W, H = 1920, 1080


class FullResolution:
    """The detector as it was before the reduction: gray + blur + float32 at the resolution of the camera."""

    def __init__(self, trigger: PresenceTrigger):
        self._roi, self._diff = trigger.roi, trigger.diff_threshold
        self._min_area, self._motion_area = trigger.min_area, trigger.motion_area
        self._background = self._previous = None
        self._still_since = self._absent_since = None
        self._present = False

    def _crop(self, image):
        h, w = image.shape[:2]
        x0, y0, x1, y1 = self._roi
        region = image[int(y0 * h) : max(int(y1 * h), int(y0 * h) + 1), int(x0 * w) : max(int(x1 * w), int(x0 * w) + 1)]
        gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY) if region.ndim == 3 else region
        return cv2.GaussianBlur(gray, (5, 5), 0).astype(np.float32)

    def update(self, image, t):
        roi = self._crop(image)
        if self._background is None:
            self._background = roi.copy()
        present_area = float((np.abs(roi - self._background) > self._diff).mean())
        moving_area = float((np.abs(roi - self._previous) > self._diff).mean()) if self._previous is not None else 0.0
        self._previous = roi
        present, moving = present_area >= self._min_area, moving_area >= self._motion_area
        if not present:
            cv2.accumulateWeighted(roi, self._background, BACKGROUND_RATE)
        if present != self._present or self._absent_since is None:
            self._absent_since = None if present else t
        self._present = present
        if present and not moving:
            if self._still_since is None:
                self._still_since = t
        else:
            self._still_since = None
        return (
            present,
            moving,
            0.0 if self._still_since is None else t - self._still_since,
            0.0 if self._absent_since is None else t - self._absent_since,
        )


def trigger(**kw):
    return PresenceTrigger.model_validate(
        {"roi": [0, 0, 1, 1], "still_ms": 400, "rearm": "object_absent", "diff_threshold": 25, "min_area": 0.05, "motion_area": 0.01, **kw}
    )


def _background(kind: str, rng) -> np.ndarray:
    if kind == "smooth":
        base = cv2.GaussianBlur(rng.integers(60, 120, (H, W, 3), dtype=np.uint8), (0, 0), 25)
    elif kind == "fine":  # a printed pattern: one-pixel lines, where a reduction can differ from a blur
        base = np.full((H, W, 3), 90, np.uint8)
        base[::2, :, :] = 150
        base[:, ::3, :] = 60
    else:
        base = np.full((H, W, 3), 100, np.uint8)
    return base


def _sequence(kind: str, seed: int = 1):
    """Frames of an empty scene with sensor noise, a textured box that comes in, slides, stops and leaves, and slow light drift."""
    rng = np.random.default_rng(seed)
    base = _background(kind, rng)
    box = rng.integers(140, 230, (360, 520, 3), dtype=np.uint8)

    def frame(x: int | None, gain: int = 0):
        image = base.astype(np.int16) + gain + rng.integers(-3, 4, base.shape, dtype=np.int16)
        if x is not None:
            image[300:660, x : x + 520] = box
        return np.clip(image, 0, 255).astype(np.uint8)

    frames = [frame(None) for _ in range(4)]
    frames += [frame(x) for x in (200, 500, 800, 900, 940, 940, 940, 940, 940, 940)]  # in, sliding, still
    frames += [frame(None) for _ in range(4)]  # out
    frames += [frame(None, gain=i // 3) for i in range(1, 25)]  # light drift
    frames += [frame(300) for _ in range(5)]  # back in, at the edge of a small region
    return frames


@pytest.mark.parametrize("kind", ["smooth", "fine", "flat"])
@pytest.mark.parametrize("roi", [[0, 0, 1, 1], [0.2, 0.2, 0.8, 0.8], [0.0, 0.0, 0.2, 0.3], [0.1, 0.25, 0.55, 0.7]])
def test_the_reduced_detector_decides_what_the_full_resolution_one_decided(kind, roi):
    spec = trigger(roi=roi)
    old, new = FullResolution(spec), PresenceDetector(spec)
    for i, image in enumerate(_sequence(kind)):
        t = i * 0.1
        want = old.update(image, t)
        got = new.update(image, t)
        assert (got.present, got.moving) == want[:2], f"frame {i}: {got} vs {want}"
        assert got.still_for_s == pytest.approx(want[2]) and got.absent_for_s == pytest.approx(want[3]), f"frame {i}"


@pytest.mark.parametrize("limits", [(8, 0.02, 0.005), (12, 0.05, 0.01), (40, 0.3, 0.05)])
def test_tight_thresholds_decide_the_same_too(limits):
    """Down to a change of 8 gray levels over 2 % of the area. Below the noise of the camera (here ±3 levels, with a 6-level
    threshold) the reduced picture is the quieter one: the mean of the pixels it covers averages the noise out, so it does not
    react where the full-resolution one reacted to the noise itself; that is not a case a job should be configured for."""
    diff, area, motion = limits
    spec = trigger(roi=[0.1, 0.25, 0.55, 0.7], diff_threshold=diff, min_area=area, motion_area=motion)
    for kind in ("smooth", "fine"):
        old, new = FullResolution(spec), PresenceDetector(spec)
        for i, image in enumerate(_sequence(kind, seed=2)):
            want, got = old.update(image, i * 0.1), new.update(image, i * 0.1)
            assert (got.present, got.moving) == want[:2], f"{kind} frame {i}"


def test_a_small_region_is_not_enlarged():
    """A region already small is compared pixel by pixel, as before."""
    spec = trigger(roi=[0.4, 0.4, 0.55, 0.6])
    old, new = FullResolution(spec), PresenceDetector(spec)
    for i, image in enumerate(_sequence("smooth", seed=4)):
        want, got = old.update(image, i * 0.1), new.update(image, i * 0.1)
        assert (got.present, got.moving) == want[:2]
