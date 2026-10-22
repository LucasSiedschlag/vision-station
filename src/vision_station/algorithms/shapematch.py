"""Shape matching: find a taught pattern by the direction of its edges, turned and scaled (TD-25, architecture §15.4).

The method is the published one of Steger ("Occlusion, clutter, and illumination invariant object recognition", 2002): the model
is a set of points on the edges of the template with the direction of the gradient there, and a pose scores by how well the
directions of the picture agree at the model's points, `s = mean(d_model . d_picture)`. It does not depend on the brightness (the
directions are normalised), tolerates a part hidden (the score falls by the share hidden) and noise.

How it is made fast, over a pyramid of pictures each half the size of the one below:

- the **model** is built once, with a point set per level; a turned and scaled model is the same points moved and their directions
  turned, so no picture is resampled;
- on the **top level** every pose (angle and scale, in steps that move the farthest point a pixel) is scored at every position
  at once, by cross-correlating the picture's direction field with the model's (`cv2.matchTemplate`, FFT). That map only finds
  candidates: its numbers come from points rounded to pixels;
- each candidate is **refined** down the levels by scoring the model directly at float positions in the picture
  (bilinear sampling of the direction field, float64), moving x, y, the angle and the scale while the score rises, and at the
  full resolution with steps halved four times. Those scores are smooth in the pose, so they are repeatable (V9) and the pose is
  good to a tenth of a pixel and of a degree.

Coordinates are pixel-centre coordinates (the index of the pixel); an angle is counter-clockwise on the screen, in degrees, like
a fixture's. The pattern must lie entirely inside the picture to be found at the top level. Own implementation with OpenCV and NumPy.
"""

import math
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal

import cv2
import numpy as np

from vision_station.algorithms.levels import gray_of

MAX_LEVELS = 4
MIN_POINTS = 30  # a level with fewer model points is not used
MIN_SIDE = 10  # ...nor one whose template is smaller than this
POINT_CAPS = (1000, 500, 250, 200)  # model points kept at level 0, 1, 2, 3
WEAK = 3.0  # gray levels per pixel: under this the picture has no direction
STRONG = 6.0  # the least gradient of a model point
STRONG_SHARE = 0.2  # ...and its share of the 98th percentile of the gradient of the template
TOP_STEP = 2.0  # on the top level the poses are this many pixels apart at the farthest point
MAX_POSES = 4000
WINDOW_MARGIN = 12  # pixels around the farthest point of the model in the window of a level that is not made whole
FINE_ROUNDS = 4  # at the full resolution the steps are halved this many times

Polarity = Literal["same", "ignore"]


@dataclass(frozen=True)
class Match:
    x: float  # the centre of the template in the picture
    y: float
    angle: float  # degrees, counter-clockwise on the screen
    scale: float
    score: float  # 0..1


@dataclass(frozen=True)
class _Level:
    points: np.ndarray  # n x 2, float64: relative to the centre of the template, in the pixels of this level
    dirs: np.ndarray  # n x 2, unit vectors
    radius: float  # of the farthest point


@dataclass(frozen=True)
class ShapeModel:
    levels: tuple[_Level, ...]  # [0] is the full resolution
    size: tuple[int, int]  # width and height of the template


def _gradient(gray: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """A central difference per pixel: the Sobel 3 x 3 over 8."""
    return cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3) / 8.0, cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3) / 8.0


def _pyramid(gray: np.ndarray, levels: int) -> list[np.ndarray]:
    pyramid = [gray.astype(np.float32)]
    for _ in range(levels - 1):
        pyramid.append(cv2.pyrDown(pyramid[-1]))
    return pyramid


def _field(gray: np.ndarray) -> np.ndarray:
    """The direction of the gradient at every pixel as a unit vector (x, y); zero where the picture is flat."""
    gx, gy = _gradient(gray)
    magnitude = np.hypot(gx, gy)
    scale = np.where(magnitude >= WEAK, 1.0 / np.maximum(magnitude, 1e-6), 0.0).astype(np.float32)
    return np.dstack([gx * scale, gy * scale])


def _thin(points: np.ndarray, strength: np.ndarray, cap: int) -> np.ndarray:
    """The indices of at most `cap` points, the strongest of each cell of a grid whose cells grow until the count fits."""
    if len(points) <= cap:
        return np.arange(len(points))
    cell = 1
    while True:
        cell += 1
        cells = (np.floor(points[:, 0] / cell).astype(np.int64) * 100003) + np.floor(points[:, 1] / cell).astype(np.int64)
        order = np.lexsort((-strength, cells))  # by cell, the strongest first
        first = np.ones(len(order), bool)
        first[1:] = cells[order][1:] != cells[order][:-1]
        chosen = np.sort(order[first])
        if len(chosen) <= cap:
            return chosen


def _level(gray: np.ndarray, level: int, centre: tuple[float, float]) -> _Level | None:
    gx, gy = _gradient(gray)
    magnitude = np.hypot(gx, gy)
    inner = np.zeros(magnitude.shape, bool)
    inner[2:-2, 2:-2] = True  # the border of a Sobel is not an edge
    if not inner.any():
        return None
    threshold = max(STRONG, STRONG_SHARE * float(np.percentile(magnitude[inner], 98)))
    ys, xs = np.nonzero(inner & (magnitude >= threshold))
    if len(xs) < MIN_POINTS:
        return None
    keep = _thin(np.column_stack([xs, ys]).astype(np.float64), magnitude[ys, xs], POINT_CAPS[level])
    xs, ys = xs[keep], ys[keep]
    m = magnitude[ys, xs].astype(np.float64)
    points = np.column_stack([xs - centre[0], ys - centre[1]]).astype(np.float64)
    dirs = np.column_stack([gx[ys, xs] / m, gy[ys, xs] / m])
    return _Level(points, dirs, float(np.hypot(points[:, 0], points[:, 1]).max()))


def build_model(template: np.ndarray) -> ShapeModel:
    """The model of a template (gray or colour). Raises `ValueError` when it is smaller than 12 pixels or flat: with too few edges
    to match by (a model needs at least 30 points)."""
    gray = gray_of(template)
    height, width = gray.shape[:2]
    if min(height, width) < MIN_SIDE:
        raise ValueError(f"the template is smaller than {MIN_SIDE} pixels")
    pyramid = _pyramid(gray, MAX_LEVELS)
    levels: list[_Level] = []
    for k, image in enumerate(pyramid):
        if min(image.shape[:2]) < MIN_SIDE:
            break
        found = _level(image, k, ((width - 1) / 2 / 2**k, (height - 1) / 2 / 2**k))
        if found is None:
            break
        levels.append(found)
    if not levels:
        raise ValueError("the template is flat or has too few edges to match by")
    return ShapeModel(tuple(levels), (width, height))


@lru_cache(maxsize=16)
def _model_of(png: bytes) -> ShapeModel:
    image = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise ValueError("not an image")
    return build_model(image)


def model_from_png(png: bytes) -> ShapeModel:
    """`build_model` of a template kept as the bytes of a PNG, cached by those bytes: a model is built once, not on every picture."""
    return _model_of(png)


def _turned(level: _Level, angle: float, scale: float) -> tuple[np.ndarray, np.ndarray]:
    """The points of the model scaled by `scale` and turned by `angle` degrees counter-clockwise on the screen, and their directions."""
    a = math.radians(angle)
    c, s = math.cos(a), math.sin(a)
    x, y = level.points[:, 0] * scale, level.points[:, 1] * scale
    dx, dy = level.dirs[:, 0], level.dirs[:, 1]
    return np.column_stack([x * c + y * s, -x * s + y * c]), np.column_stack([dx * c + dy * s, -dx * s + dy * c])


def _scores(field: np.ndarray, level: _Level, poses: np.ndarray) -> np.ndarray:
    """The score of the model at each pose (m x 4: x, y, angle in degrees, scale): the mean over its points of the dot product of
    its direction with the direction of the picture, sampled bilinearly. `field` is padded by a pixel of zeros, so a point outside the
    picture counts as zero but stays in the mean."""
    a = np.radians(poses[:, 2])[:, None]
    c, s = np.cos(a), np.sin(a)
    px, py = level.points[None, :, 0] * poses[:, 3:4], level.points[None, :, 1] * poses[:, 3:4]
    x = poses[:, 0:1] + px * c + py * s + 1.0
    y = poses[:, 1:2] - px * s + py * c + 1.0
    dx = level.dirs[None, :, 0] * c + level.dirs[None, :, 1] * s
    dy = -level.dirs[None, :, 0] * s + level.dirs[None, :, 1] * c
    h, w = field.shape[:2]
    x0, y0 = np.floor(x).astype(np.int64), np.floor(y).astype(np.int64)
    inside = (x0 >= 0) & (y0 >= 0) & (x0 < w - 1) & (y0 < h - 1)
    x0, y0 = np.clip(x0, 0, w - 2), np.clip(y0, 0, h - 2)
    fx, fy = x - x0, y - y0
    w00, w10, w01, w11 = (1 - fx) * (1 - fy), fx * (1 - fy), (1 - fx) * fy, fx * fy
    gx = field[y0, x0, 0] * w00 + field[y0, x0 + 1, 0] * w10 + field[y0 + 1, x0, 0] * w01 + field[y0 + 1, x0 + 1, 0] * w11
    gy = field[y0, x0, 1] * w00 + field[y0, x0 + 1, 1] * w10 + field[y0 + 1, x0, 1] * w01 + field[y0 + 1, x0 + 1, 1] * w11
    return np.where(inside, gx * dx + gy * dy, 0.0).sum(axis=1) / level.points.shape[0]


def _steps(radius: float) -> tuple[float, float]:
    """Degrees and relative scale that move the farthest point of the model a pixel."""
    return math.degrees(1.0 / max(radius, 1.0)), 1.0 / max(radius, 1.0)


def _range(low: float, high: float, step: float) -> list[float]:
    if high <= low:
        return [low]
    count = max(2, math.ceil((high - low) / step) + 1)
    return [float(v) for v in np.linspace(low, high, count)]


class _Pose:
    __slots__ = ("x", "y", "angle", "scale", "score")

    def __init__(self, x: float, y: float, angle: float, scale: float, score: float):
        self.x, self.y, self.angle, self.scale, self.score = x, y, angle, scale, score


def _refine(
    field: np.ndarray, level: _Level, pose: _Pose, steps: tuple[float, float, float], sign_free: bool, origin: tuple[float, float] = (0.0, 0.0), limit: int = 40
) -> _Pose:
    """Moves x, y, the angle and the scale by `steps` (pixels, degrees, relative scale) while the score rises, trying the 8 neighbours
    in position, both ways in the angle and the scale and the four combinations of angle and scale (they are coupled) at once.
    The score is the one of `_scores`, or its absolute value when the polarity is ignored."""
    dp, da, ds = steps
    moves = np.array(
        [(i * dp, j * dp, 0.0, 0.0) for i in (-1, 0, 1) for j in (-1, 0, 1) if i or j]
        + [(0.0, 0.0, a * da, b * ds) for a in (-1, 0, 1) for b in (-1, 0, 1) if a or b]
    )

    shift = np.array([origin[0], origin[1], 0.0, 0.0])  # `field` is a window of the picture that starts at `origin`

    def value(poses: np.ndarray) -> np.ndarray:
        v = _scores(field, level, poses - shift)
        return np.abs(v) if sign_free else v

    here = np.array([[pose.x, pose.y, pose.angle, pose.scale]])
    pose.score = float(value(here)[0])
    for _ in range(limit):
        trials = here + moves
        scores = value(trials)
        k = int(np.argmax(scores))
        if scores[k] <= pose.score + 1e-9:
            break
        here = trials[k : k + 1]
        pose.score = float(scores[k])
    pose.x, pose.y, pose.angle, pose.scale = (float(v) for v in here[0])
    return pose


class _Fields:
    """The direction fields of the levels of a picture. The small levels are made whole; the large ones (0 and 1), which cost most,
    only in a window around the pose that is being refined, so a picture is never differentiated at full size."""

    WHOLE_FROM = 2

    def __init__(self, pyramid: list[np.ndarray]):
        self.pyramid = pyramid
        self.whole = {k: np.pad(_field(g), ((1, 1), (1, 1), (0, 0))) for k, g in enumerate(pyramid) if k >= self.WHOLE_FROM}

    def top(self, k: int) -> np.ndarray:
        return self.whole[k][1:-1, 1:-1] if k in self.whole else _field(self.pyramid[k])

    def window(self, k: int, level: _Level, x: float, y: float, reach: float) -> tuple[np.ndarray, tuple[float, float]]:
        """The padded field around (x, y) in level `k` and the coordinates of its first pixel."""
        if k in self.whole:
            return self.whole[k], (0.0, 0.0)
        height, width = self.pyramid[k].shape[:2]
        half = int(math.ceil(level.radius * reach)) + WINDOW_MARGIN
        x0, y0 = max(0, int(math.floor(x)) - half), max(0, int(math.floor(y)) - half)
        x1, y1 = min(width, int(math.ceil(x)) + half + 1), min(height, int(math.ceil(y)) + half + 1)
        return np.pad(_field(self.pyramid[k][y0:y1, x0:x1]), ((1, 1), (1, 1), (0, 0))), (float(x0), float(y0))


def _candidates(
    fields: np.ndarray, level: _Level, angles: list[float], scales: list[float], threshold: float, sign_free: bool, wanted: int
) -> list[_Pose]:
    """The poses that score at least `threshold` somewhere on the top level, best first, the ones within half the model's radius
    of a better one dropped, at most `wanted` of them. Positions are in the pixels of that level."""
    height, width = fields.shape[:2]
    found: list[_Pose] = []
    kernel = np.ones((5, 5), np.uint8)
    for angle in angles:
        for scale in scales:
            points, dirs = _turned(level, angle, scale)
            reach_x = int(math.ceil(float(np.abs(points[:, 0]).max()))) + 1
            reach_y = int(math.ceil(float(np.abs(points[:, 1]).max()))) + 1
            # A long model fits a narrow region and may lie beside its boundary (VIA-0130).
            # The correlation origin must follow each axis of the rotated model independently.
            tw, th = 2 * reach_x + 1, 2 * reach_y + 1
            if tw > width or th > height:
                continue
            template = np.zeros((th, tw, 2), np.float32)
            ix = np.round(points[:, 0]).astype(int) + reach_x
            iy = np.round(points[:, 1]).astype(int) + reach_y
            np.add.at(template[:, :, 0], (iy, ix), dirs[:, 0].astype(np.float32))
            np.add.at(template[:, :, 1], (iy, ix), dirs[:, 1].astype(np.float32))
            result = cv2.matchTemplate(fields, template, cv2.TM_CCORR) / len(points)
            magnitude = np.abs(result) if sign_free else result
            peaks = (magnitude >= threshold) & (magnitude >= cv2.dilate(magnitude, kernel))
            for y, x in zip(*np.nonzero(peaks), strict=True):
                found.append(_Pose(float(x + reach_x), float(y + reach_y), angle, scale, float(magnitude[y, x])))
    found.sort(key=lambda p: (-p.score, p.y, p.x, p.angle, p.scale))
    kept: list[_Pose] = []
    near = max(3.0, 0.5 * level.radius)
    for pose in found:
        if all(math.hypot(pose.x - k.x, pose.y - k.y) > near for k in kept):
            kept.append(pose)
            if len(kept) >= wanted:
                break
    return kept


def find_shapes(
    image: np.ndarray,
    model: ShapeModel,
    *,
    angles: tuple[float, float] = (-20.0, 20.0),
    scales: tuple[float, float] = (0.9, 1.1),
    min_score: float = 0.7,
    max_instances: int = 1,
    polarity: Polarity = "same",
) -> list[Match]:
    """The instances of the model in `image` with a score of at least `min_score`, best first, at most `max_instances`, each a pose
    in the picture. The angle is searched in `angles` degrees and the scale in `scales`. With `polarity` `ignore` a pattern with its
    light and dark reversed matches too. Nothing found is an empty list."""
    if not (angles[0] <= angles[1] and 0 < scales[0] <= scales[1]):
        raise ValueError("angles and scales are ranges, low to high, with a scale above 0")
    if image.size == 0:
        return []
    gray = gray_of(image)
    levels = len(model.levels)
    pyramid = _pyramid(gray, levels)
    if min(pyramid[-1].shape[:2]) < 3:
        return []
    fields = _Fields(pyramid)
    sign_free = polarity == "ignore"
    top = levels - 1
    da, ds = (TOP_STEP * v for v in _steps(model.levels[top].radius))  # coarser than a pixel: the refinement corrects it
    pose_angles, pose_scales = _range(angles[0], angles[1], da), _range(scales[0], scales[1], ds)
    if len(pose_angles) * len(pose_scales) > MAX_POSES:
        raise ValueError("too many poses: narrow the range of angles or scales")
    reach = max(1.0, scales[1]) * 1.05
    relaxed = min_score - 0.15
    wanted = max(10, 4 * max_instances)
    candidates = _candidates(fields.top(top), model.levels[top], pose_angles, pose_scales, relaxed, sign_free, wanted)
    refined: list[_Pose] = []
    for pose in candidates:
        alive = True
        for k in range(top, -1, -1):
            if k < top:
                pose.x, pose.y = pose.x * 2, pose.y * 2
            level = model.levels[k]
            step_a, step_s = _steps(level.radius)
            field, origin = fields.window(k, level, pose.x, pose.y, reach)
            pose = _refine(field, level, pose, (1.0, step_a, step_s), sign_free, origin)
            if pose.score < relaxed:  # a false candidate dies at the first level that shows it, not after the last
                alive = False
                break
        if alive:
            refined.append(pose)
    refined.sort(key=lambda p: (-round(p.score, 3), p.y, p.x, p.angle, p.scale))  # scores equal to a thousandth: by position
    survivors: list[_Pose] = []
    near = max(4.0, 0.5 * model.levels[0].radius)
    for pose in refined:
        if pose.score >= min_score and all(math.hypot(pose.x - k.x, pose.y - k.y) > near for k in survivors):
            survivors.append(pose)
        if len(survivors) >= max_instances:
            break
    step_a, step_s = _steps(model.levels[0].radius)
    out: list[Match] = []
    for pose in survivors:
        field, origin = fields.window(0, model.levels[0], pose.x, pose.y, reach)
        for r in range(1, FINE_ROUNDS + 1):  # the steps halved: the pose to a fraction of a pixel and of a degree
            pose = _refine(field, model.levels[0], pose, (1.0 / 2**r, step_a / 2**r, step_s / 2**r), sign_free, origin)
        if pose.score >= min_score and angles[0] - step_a <= pose.angle <= angles[1] + step_a and scales[0] - step_s <= pose.scale <= scales[1] + step_s:
            out.append(Match(pose.x, pose.y, ((pose.angle + 180.0) % 360.0) - 180.0, pose.scale, min(1.0, pose.score)))
    out.sort(key=lambda m: (-round(m.score, 3), m.y, m.x))
    return out
