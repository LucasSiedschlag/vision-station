import numpy as np
import yaml

from validation.case import Case, Golden, Scene
from vision_station.core.calibration import CALIBRATION_FILE
from validation.scenes import bench

_BAD = ({}, {"mode": "color"}, {"mode": "dark", "min_area": 0.9, "max_area": 0.1}, {"mode": "dark", "search": [0.8, 0, 0.2, 1]})
_FRAME, _RECT = bench(printed=False)
_AWAY, _AWAY_RECT = bench(printed=False, h=60, w=100, at=(50, 300))


def _goldens():
    return (
        Golden("a small part away from the centre", _AWAY, {"min_area": 0.005}, rect=_AWAY_RECT, tolerance=2 / 640),
        Golden("an empty bench", bench(printed=False, at=(-1, -1))[0]),
    )


LOCATORS = {
    1: Case(params={"mode": "dark"}, bad_params=_BAD, scene=Scene(_FRAME, _RECT), goldens=_goldens()),
    2: Case(params={"mode": "dark"}, bad_params=_BAD, scene=Scene(_FRAME, _RECT), goldens=_goldens()),
}


def squares(*spots, size=20, dark=False):
    """A 200 x 200 picture, black with a white square at each (x, y); `dark`: the other way round."""
    image = np.zeros((200, 200), np.uint8)
    for x, y in spots:
        image[y : y + size, x : x + size] = 255
    return 255 - image if dark else image


THREE = squares((30, 30), (100, 30), (30, 120))  # 400 px each
HALF_MM = {CALIBRATION_FILE: yaml.safe_dump({"method": "known_dimension", "mm_per_px": 0.5, "date": "2026-10-22"}).encode()}  # 400 px = 100 mm²
FOUND = ("poly", "found")


def box(x, y, size=20):
    return (x, y, x + size - 1, y + size - 1)


TOOLS = {1: Case(
    params={"mode": "light", "min_count": 2},
    bad_params=(
        {"mode": "light"},  # no limit to judge by
        {"mode": "color", "min_count": 1},  # needs a colour
        {"mode": "light", "min_count": 3, "max_count": 1},
        {"mode": "light", "min_area": 10, "max_area": 1},
        {"mode": "light", "min_count": 1, "filter_min": 50, "filter_max": 10},
        {"mode": "light", "min_count": 1, "threshold": 300},
        {"mode": "light", "min_count": 1, "unknown": 1},
    ),
    passing=THREE,
    failing=np.zeros((200, 200), np.uint8),
    nothing_on_fail="it fails by not finding any blob: there is no outline to draw",
    goldens=(
        Golden("three squares of 400 px, three asked", THREE, {"min_count": 3, "max_count": 3}, passed=True,
               values={"count": 3, "area": 1200, "largest": 400}, tolerance=0,
               marks=((*FOUND, box(30, 30)), (*FOUND, box(100, 30)), (*FOUND, box(30, 120)))),
        Golden("three squares, four asked", THREE, {"min_count": 4}, passed=False, values={"count": 3}, tolerance=0,
               marks=((*FOUND, box(30, 30)), (*FOUND, box(100, 30)), (*FOUND, box(30, 120)))),
        Golden("dark squares on a light region", squares((30, 30), (100, 30), dark=True), {"mode": "dark", "min_count": 2, "max_count": 2}, passed=True,
               values={"count": 2, "area": 800}, tolerance=0),
        Golden("a speck under the filter does not count", squares((30, 30), (150, 150), size=3), {"filter_min": 20, "min_count": 0, "max_count": 0}, passed=True,
               values={"count": 0}, tolerance=0, marks=()),
        Golden("a part larger than allowed is the defect", np.maximum(THREE, squares((120, 120), size=60)), {"max_largest": 1000}, passed=False,
               values={"count": 4, "largest": 3600}, tolerance=0, marks=(("poly", "defect", box(120, 120, 60)), ("poly", "defect", box(30, 30)), ("poly", "defect", box(100, 30)), ("poly", "defect", box(30, 120)))),
        Golden("too many blobs", THREE, {"min_count": 0, "max_count": 2}, passed=False, values={"count": 3}, tolerance=0,
               marks=(("poly", "defect", box(30, 30)), ("poly", "defect", box(100, 30)), ("poly", "defect", box(30, 120)))),
        Golden("the area in square millimetres of a calibrated job", THREE, {"min_count": 0, "max_area_mm2": 250}, HALF_MM, passed=False,
               values={"area": 1200, "area_mm2": 300, "largest_mm2": 100}, tolerance=0),
        Golden("a calibrated job reports both areas", THREE, {"min_count": 3}, HALF_MM, passed=True, values={"area": 1200, "area_mm2": 300}, tolerance=0),
        Golden("a filter in square millimetres", np.maximum(THREE, squares((120, 120), size=60)), {"min_count": 3, "max_count": 3, "filter_max_mm2": 150}, HALF_MM,
               passed=True, values={"count": 3, "largest": 400}, tolerance=0),
    ),
)}
