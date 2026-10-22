"""Outlines of a mask, simplified to fit a mark (VIA-0124): pure functions, deterministic."""

import cv2
import numpy as np

from vision_station.core.results import MAX_MARK_POINTS


MAX_SIDE = 1024  # a larger mask is outlined smaller: a mark needs no sub-pixel precision, and a 4 MP mask costs a quarter


def mask_outlines(mask: np.ndarray, most: int = 16, max_points: int = MAX_MARK_POINTS) -> list[tuple[tuple[float, float], ...]]:
    """The outer outlines of the white parts of `mask`, the largest first, at most `most` of them and `max_points` points each.
    A dot has none; a line is an outline of two points. The outline is simplified, never cut."""
    if mask.size == 0:
        return []
    binary = np.ascontiguousarray(mask, dtype=np.uint8)
    shrink = min(1.0, MAX_SIDE / max(binary.shape[:2]))
    if shrink < 1.0:  # any coverage keeps the pixel, so a thin line stays a line
        binary = (cv2.resize(binary, None, fx=shrink, fy=shrink, interpolation=cv2.INTER_AREA) > 0).astype(np.uint8)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    # the areas first, so a noisy mask with thousands of specks costs a count, not a contour for each
    body = stats[1:]
    order = (np.lexsort((body[:, cv2.CC_STAT_LEFT], body[:, cv2.CC_STAT_TOP], -body[:, cv2.CC_STAT_AREA]))[:most] + 1).tolist()
    out: list[tuple[tuple[float, float], ...]] = []
    for i in order:
        x, y, w, h = (int(stats[i, k]) for k in (cv2.CC_STAT_LEFT, cv2.CC_STAT_TOP, cv2.CC_STAT_WIDTH, cv2.CC_STAT_HEIGHT))
        part = (labels[y : y + h, x : x + w] == i).astype(np.uint8)
        found, _ = cv2.findContours(part, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contour = max(found, key=cv2.contourArea) + (x, y)
        epsilon = 0.005 * cv2.arcLength(contour, True)
        points = contour
        while len(points) > max_points:
            points = cv2.approxPolyDP(contour, epsilon, True)
            epsilon = max(epsilon * 2, 1.0)
        if len(points) >= 2:  # a line (a scratch) is an outline of two points
            out.append(tuple((float(px) / shrink, float(py) / shrink) for px, py in points.reshape(-1, 2)))
    return out
