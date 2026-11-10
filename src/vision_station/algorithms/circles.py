"""Round parts: the circles in a picture, found with the Hough transform on a contrast-normalised region (FR-PLT-9).

A bright metal ring on cardboard has a different contrast under each light, and its inner and outer edges are both circles.
Two things make the count steady: the gray levels are first equalised in small tiles (CLAHE), so the same edge votes the same
under a dimmer or a harsher light, and a circle that lies within `min_distance` of a better one is dropped here (OpenCV's own
`minDist` leaves the same centre twice at two radii, once for each edge of a ring).
"""

from dataclasses import dataclass

import cv2
import numpy as np

MAX_CIRCLES = 200  # a region with more than this is not a region of rings
CLAHE_CLIP = 3.0  # fixed: it is what makes the score mean the same under each light, so it is not a job's business
CLAHE_TILES = 8
BLUR_PX = 5  # a blur of the region's gray levels before the votes
EDGE_STRENGTH = 300.0  # the strongest edge (the upper Canny threshold) that makes a vote, after the equalisation
ACCUMULATOR_STEP = 1.5  # the votes are counted on a grid 1.5 times coarser than the picture


@dataclass(frozen=True)
class Circle:
    x: float  # the centre, in the pixels of the region
    y: float
    r: float  # the radius


def gray_of(image: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image


def find_circles(image: np.ndarray, radius_min: int, radius_max: int, min_distance: float, min_roundness: float) -> list[Circle]:
    """The circles of a radius from `radius_min` to `radius_max` pixels, best first, no two with centres closer than
    `min_distance`. `min_roundness` is 0 to 1: how perfect a circle must be (1 is a perfect one, lower finds more, and more that
    are not circles). A region too small to hold a circle of `radius_min` has none."""
    height, width = image.shape[:2]
    if min(height, width) < 2 * radius_min or radius_max < radius_min:
        return []
    gray = gray_of(image)
    if gray.dtype != np.uint8:
        gray = np.clip(gray, 0, 255).astype(np.uint8)
    gray = cv2.GaussianBlur(cv2.createCLAHE(CLAHE_CLIP, (CLAHE_TILES, CLAHE_TILES)).apply(gray), (BLUR_PX, BLUR_PX), 1.2)
    found = cv2.HoughCircles(gray, cv2.HOUGH_GRADIENT_ALT, dp=ACCUMULATOR_STEP, minDist=min_distance, param1=EDGE_STRENGTH,
                             param2=min_roundness, minRadius=radius_min, maxRadius=radius_max)
    if found is None:
        return []
    kept: list[Circle] = []
    for x, y, r in found[0].tolist():  # best first: a worse circle on a better one's ground is dropped
        if all((x - c.x) ** 2 + (y - c.y) ** 2 >= min_distance**2 for c in kept):
            kept.append(Circle(x, y, r))
            if len(kept) == MAX_CIRCLES:
                break
    return kept
