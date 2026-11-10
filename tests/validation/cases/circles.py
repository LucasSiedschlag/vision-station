import cv2
import numpy as np

from validation.case import Case, Golden

RADIUS = 24
PARAMS = {"radius_min": 18, "radius_max": 32, "min_count": 2, "max_count": 5}
FOUND = ("poly", "found")


def rings(*centres, radius=RADIUS, thick=5, double=False):
    """A flat gray picture (200 x 300) with a bright ring of `radius` and `thick` pixels at each (x, y); `double`: a second, smaller
    ring inside each, as a metal ring has an inner and an outer edge."""
    image = np.full((200, 300), 110, np.uint8)
    for x, y in centres:
        cv2.circle(image, (x, y), radius, 210, thick, cv2.LINE_AA)
        if double:
            cv2.circle(image, (x, y), radius - 9, 210, 2, cv2.LINE_AA)
    return image


def box(x, y, radius=RADIUS):
    return (x - radius, y - radius, x + radius, y + radius)


THREE = rings((60, 60), (150, 60), (240, 140))
SPOTS = ((50, 50), (130, 50), (210, 50), (50, 140), (130, 140), (210, 140), (270, 100))

TOOLS = {1: Case(
    params=PARAMS,
    bad_params=(
        {},  # no radius
        {"radius_min": 10, "min_count": 1},  # no largest radius
        {"radius_min": 10, "radius_max": 20},  # no limit to judge by
        {"radius_min": 30, "radius_max": 10, "min_count": 1},
        {"radius_min": 1, "radius_max": 10, "min_count": 1},  # too small to be a circle
        {"radius_min": 10, "radius_max": 20, "min_count": 3, "max_count": 1},
        {"radius_min": 10, "radius_max": 20, "min_count": 1, "min_roundness": 0},
        {"radius_min": 10, "radius_max": 20, "min_count": 1, "min_roundness": 1.5},
        {"radius_min": 10, "radius_max": 20, "min_count": 1, "min_distance": 0},
        {"radius_min": 10, "radius_max": 20, "min_count": 1, "unknown": 1},
    ),
    passing=THREE,
    failing=np.full((200, 300), 110, np.uint8),
    nothing_on_fail="it fails by not finding any circle: there is nothing to draw",
    goldens=(
        Golden("three rings, three asked", THREE, {"min_count": 3, "max_count": 3}, passed=True, values={"count": 3}, tolerance=0,
               marks=((*FOUND, box(60, 60)), (*FOUND, box(150, 60)), (*FOUND, box(240, 140))), mark_tolerance=3),
        Golden("three rings, four asked", THREE, {"min_count": 4}, passed=False, values={"count": 3}, tolerance=0),
        Golden("too many rings are the defect", THREE, {"min_count": 0, "max_count": 2}, passed=False, values={"count": 3}, tolerance=0,
               marks=(("poly", "defect", box(60, 60)), ("poly", "defect", box(150, 60)), ("poly", "defect", box(240, 140))), mark_tolerance=3),
        Golden("the inner and the outer edge of a ring are one circle", rings((60, 60), (150, 60), (240, 140), double=True), {"min_count": 3, "max_count": 3},
               passed=True, values={"count": 3}, tolerance=0),
        Golden("seven rings, the most there can be here", rings(*SPOTS), {"min_count": 7, "max_count": 7}, passed=True, values={"count": 7}, tolerance=0),
        Golden("rings far from the size asked are not counted", rings((60, 60), (150, 60), radius=45), {"radius_min": 18, "radius_max": 32, "min_count": 0, "max_count": 0},
               passed=True, values={"count": 0}, tolerance=0),
        Golden("a flat region has no circle", np.full((200, 300), 110, np.uint8), {"min_count": 0, "max_count": 0}, passed=True, values={"count": 0, "radius": 0}, tolerance=0, marks=()),
        Golden("a region too small to hold a circle has none", np.full((20, 20), 110, np.uint8), {"min_count": 0, "max_count": 0}, passed=True, values={"count": 0}, tolerance=0),
        Golden("a dimmer light counts the same", (THREE * 0.5).astype(np.uint8), {"min_count": 3, "max_count": 3}, passed=True, values={"count": 3}, tolerance=0),
    ),
)}
