"""A tool's marks, from the pixels of its region to fractions of the frame (VIA-0124, FR-PLT-10).

Marks only explain a result, they never decide it: a mark that is not valid is dropped and logged, the verdict stays.
`valid_mark` is the one rule, used here and by the V7 check of the validation bench.
"""

import logging
import math
from collections.abc import Iterable

import numpy as np

from vision_station.core.results import MAX_MARK_POINTS, MAX_MARK_TEXT, MAX_MARKS, Mark
from vision_station.geometry.pose import Cut

log = logging.getLogger(__name__)

_KINDS = {"rect": (2, 2), "poly": (2, MAX_MARK_POINTS), "point": (1, 1), "text": (1, 1)}  # the number of points
_ROLES = {"found", "expected", "defect"}
_EPS = 0.5  # half a pixel of rounding is not "outside" (geometry.pose.cut)
_DECIMALS = 4


def valid_mark(mark: Mark, shape: tuple[int, ...]) -> bool:
    """The mark has a known kind and role, the right number of finite points, all inside a region of `shape` (height, width)."""
    height, width = shape[:2]
    limits = _KINDS.get(mark.kind)
    if limits is None or mark.role not in _ROLES or not limits[0] <= len(mark.points) <= limits[1]:
        return False
    if mark.kind == "text" and not 0 < len(mark.text) <= MAX_MARK_TEXT:
        return False
    return all(
        len(p) == 2 and all(math.isfinite(v) for v in p) and -_EPS <= p[0] <= width + _EPS and -_EPS <= p[1] <= height + _EPS
        for p in mark.points
    )


def to_frame_marks(marks: Iterable[Mark], region: Cut, frame_shape: tuple[int, ...]) -> tuple[Mark, ...]:
    """The valid marks (at most `MAX_MARKS`, the tool's first ones) as fractions of the frame. A rect of a turned region is no
    longer a rect in the frame, so it becomes a closed poly of its four corners."""
    height, width = frame_shape[:2]
    matrix = region.to_frame
    turned = not np.array_equal(matrix[:, :2], np.eye(2))
    out: list[Mark] = []
    dropped = 0
    for mark in marks:
        if len(out) >= MAX_MARKS:
            dropped += 1
        elif not valid_mark(mark, region.image.shape):
            dropped += 1
        else:
            out.append(_mapped(mark, matrix, turned, width, height))
    if dropped:
        log.warning("%d mark(s) dropped (invalid, or more than %d)", dropped, MAX_MARKS)
    return tuple(out)


def _mapped(mark: Mark, matrix: np.ndarray, turned: bool, width: int, height: int) -> Mark:
    points = mark.points
    kind = mark.kind
    if kind == "rect":
        (x0, y0), (x1, y1) = points
        x0, x1, y0, y1 = min(x0, x1), max(x0, x1), min(y0, y1), max(y0, y1)
        if turned:
            kind, points = "poly", ((x0, y0), (x1, y0), (x1, y1), (x0, y1))
        else:
            points = ((x0, y0), (x1, y1))
    closed = True if kind == "poly" and mark.kind == "rect" else mark.closed
    pts = np.array([[x, y, 1.0] for x, y in points]) @ matrix.T
    mapped = tuple((round(float(x) / width, _DECIMALS), round(float(y) / height, _DECIMALS)) for x, y in pts)
    return Mark(kind, mark.role, mapped, closed, mark.text)
