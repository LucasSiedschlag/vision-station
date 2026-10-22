"""Calipers: edges along a profile, to a fraction of a pixel (pure functions, architecture §15.4).

A caliper looks at a strip and finds where the gray level steps. The strip is averaged across (the noise falls with its
width) into a 1-D profile, which is smoothed and differentiated with the derivative of a Gaussian; the edges are the peaks
of that gradient, and a Gaussian fit through the peak and its two neighbours gives the position between pixels and the height.

Positions are in **pixel-centre coordinates**: the centre of pixel `i` is `i`, so the edge between pixel 19 and pixel 20 is
at 19.5, and the distance from the start of the strip to an edge at `p` is `p + 0.5`. `rising` is dark to light in the
direction of the profile (left to right, or top to bottom).
"""

import math
from dataclasses import dataclass
from typing import Literal

import cv2
import numpy as np

from vision_station.algorithms.levels import gray_of

Polarity = Literal["any", "rising", "falling"]


@dataclass(frozen=True)
class Edge:
    position: float  # pixel-centre coordinates along the profile
    rising: bool  # dark to light
    contrast: float  # the height of the step in gray levels (> 0)


def profile(region: np.ndarray, axis: Literal["x", "y"]) -> np.ndarray:
    """The mean gray level of the strip along `axis`: one value per column (`x`) or per row (`y`)."""
    gray = gray_of(region).astype(np.float64)
    return gray.mean(axis=0) if axis == "x" else gray.mean(axis=1)


def gradient(values: np.ndarray, sigma: float) -> np.ndarray:
    """The derivative of the profile smoothed by a Gaussian of `sigma` pixels, scaled by `sigma * sqrt(2 pi)` so that a step
    of height `h` peaks at `h` (the convention of the amplitude of a measure in machine vision)."""
    radius = max(1, math.ceil(4 * sigma))
    offsets = np.arange(-radius, radius + 1, dtype=np.float64)
    kernel = -offsets / sigma**2 * np.exp(-(offsets**2) / (2 * sigma**2)) / (sigma * math.sqrt(2 * math.pi))
    padded = np.pad(np.asarray(values, dtype=np.float64), radius, mode="edge")  # a flat border: no step is invented there
    return np.convolve(padded, kernel, mode="valid") * sigma * math.sqrt(2 * math.pi)


def _peak(before: float, at: float, after: float) -> tuple[float, float]:
    """Where, in pixels from the middle sample, and how high the peak through three samples of a gradient is. The samples of a
    Gaussian-smoothed step are a Gaussian, whose logarithm is a parabola: that fit is exact for a step and keeps its height; a
    sample of zero falls back to the parabola of the values themselves."""
    if before > 0 and after > 0:
        before, at_, after, back = math.log(before), math.log(at), math.log(after), math.exp
    else:
        at_, back = at, float
    denominator = before - 2 * at_ + after
    if denominator >= 0:
        return 0.0, at
    offset = 0.5 * (before - after) / denominator
    return offset, float(back(at_ - 0.25 * (before - after) * offset))


def find_edges(values: np.ndarray, sigma: float = 1.0, polarity: Polarity = "any", min_contrast: float = 20.0) -> list[Edge]:
    """The edges of a 1-D profile, in order along it: the peaks of the gradient with at least `min_contrast` gray levels of
    step, of the `polarity` asked, to sub-pixel position. Peaks within `ceil(3 sigma)` of an end are dropped, where the border
    bends the gradient. A profile shorter than 3 has none. Positions are in the units of the profile's index."""
    if sigma < 0.5:
        raise ValueError("sigma is at least 0.5 pixel")
    values = np.asarray(values, dtype=np.float64)
    if values.size < 3:
        return []
    g = gradient(values, sigma)
    a = np.abs(g)
    margin = math.ceil(3 * sigma)
    edges: list[Edge] = []
    for i in range(max(1, margin), values.size - max(1, margin)):
        if not (a[i] > a[i - 1] and a[i] >= a[i + 1]) or a[i] < min_contrast:  # on an exact tie the first of the two
            continue
        rising = bool(g[i] > 0)
        if (polarity == "rising" and not rising) or (polarity == "falling" and rising):
            continue
        offset, contrast = _peak(a[i - 1], a[i], a[i + 1])
        edges.append(Edge(float(i + offset), rising, float(contrast)))
    return edges


def ray_profiles(gray: np.ndarray, centre: tuple[float, float], radii: tuple[float, float], angles: np.ndarray) -> np.ndarray:
    """The gray level along rays from `centre` (x, y in pixel-centre coordinates), one row per angle in radians (counter-clockwise
    on the screen is the angle of `atan2(-dy, dx)`; here the angle is simply `x = cos`, `y = sin`, y downwards), one column per
    pixel of radius from `radii[0]` to `radii[1]`. Each profile is the mean of three parallel lines a pixel apart, so a speck
    does not make an edge. Samples outside the picture repeat its border."""
    steps = np.arange(radii[0], radii[1] + 1e-9, 1.0, dtype=np.float32)
    cos, sin = np.cos(angles).astype(np.float32)[:, None, None], np.sin(angles).astype(np.float32)[:, None, None]
    across = np.array([-1.0, 0.0, 1.0], np.float32)[None, :, None]
    xs = centre[0] + cos * steps[None, None, :] - sin * across
    ys = centre[1] + sin * steps[None, None, :] + cos * across
    flat = (xs.reshape(-1, steps.size), ys.reshape(-1, steps.size))
    sampled = cv2.remap(gray.astype(np.float32), flat[0], flat[1], cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    return sampled.reshape(len(angles), 3, steps.size).mean(axis=1).astype(np.float64)


def fit_circle(points: np.ndarray, rounds: int = 3) -> tuple[float, float, float, float, np.ndarray] | None:
    """The circle through `points` (n x 2): centre x, centre y, radius, the RMS distance of the points kept to it, and which points
    were kept. A least-squares fit (Kåsa), then points more than 3 median absolute deviations (at least half a pixel) from the
    circle are dropped and it is fitted again, up to `rounds` times, so a false edge does not bend it. None when there are fewer than
    three points, they lie on a line, or the fit is not a circle."""
    points = np.asarray(points, dtype=np.float64)
    keep = np.ones(len(points), bool)
    for _ in range(rounds + 1):
        if keep.sum() < 3:
            return None
        x, y = points[keep, 0], points[keep, 1]
        design = np.column_stack([x, y, np.ones_like(x)])
        solution, _, rank, _ = np.linalg.lstsq(design, -(x**2 + y**2), rcond=None)
        if rank < 3:
            return None
        cx, cy = -solution[0] / 2, -solution[1] / 2
        squared = cx**2 + cy**2 - solution[2]
        if not np.isfinite(squared) or squared <= 0:
            return None
        radius = float(np.sqrt(squared))
        residual = np.abs(np.hypot(points[:, 0] - cx, points[:, 1] - cy) - radius)
        spread = 1.4826 * float(np.median(np.abs(residual[keep] - np.median(residual[keep]))))
        wanted = residual <= max(3 * spread, 0.5)
        if (wanted == keep).all():
            break
        keep = wanted
    rms = float(np.sqrt(np.mean(residual[keep] ** 2)))
    return float(cx), float(cy), radius, rms, keep
