import cv2
import numpy as np
import yaml

from validation.case import Case, Golden
from vision_station.core.calibration import CALIBRATION_FILE

LOW, HIGH = 40, 200
HALF_MM = {CALIBRATION_FILE: yaml.safe_dump({"method": "known_dimension", "mm_per_px": 0.5, "date": "2026-10-22"}).encode()}


def strip(*spans, length=200, rows=40, low=LOW, high=HIGH):
    """A strip, `low` with `high` over each (start, stop) in columns: the profile is the same in every row."""
    line = np.full(length, low, np.float64)
    for start, stop in spans:
        line[start:stop] = high
    return np.tile(np.clip(np.round(line), 0, 255).astype(np.uint8), (rows, 1))


BAR = strip((20, 140))  # 120 px wide: edges at 19.5 and 139.5 (pixel centres)
FLAT = np.full((40, 200), 100, np.uint8)
COMB = strip(*((s, s + 10) for s in (20, 40, 60, 80, 100)))  # period 20
COMB_GAP = strip(*((s, s + 10) for s in (20, 40, 80, 100, 120)))  # one tooth missing: a gap of 40
STEP = strip((51, 200))
STEP[:, 50] = round(LOW + 0.7 * (HIGH - LOW))  # the step at 50.3 of a picture whose pixel i covers [i, i+1]
def _disc(radius, centre, size=(120, 120)):
    yy, xx = np.mgrid[: size[0], : size[1]].astype(np.float64)
    share = np.clip(0.5 - (np.hypot(xx - centre[0], yy - centre[1]) - radius), 0, 1)
    return np.round(LOW + (HIGH - LOW) * share).astype(np.uint8)


DISC = _disc(40, (59.5, 59.5))  # a light disc of diameter 80, its edge area-averaged
DISC_OFF = _disc(30, (50, 70))
LINE = ("poly", "found", (19.5, 0, 19.5, 39))
LINE2 = ("poly", "found", (139.5, 0, 139.5, 39))

TOOLS = {1: Case(
    params={"mode": "width", "min_distance": 60, "max_distance": 200},
    bad_params=(
        {},
        {"mode": "presence"},  # a count to judge by
        {"mode": "width"},  # a limit on the distance
        {"mode": "width", "min_distance": 50, "max_distance": 10},
        {"mode": "width", "min_distance": -1},
        {"mode": "width", "min_distance": 1, "sigma": 0.2},
        {"mode": "width", "min_distance": 1, "direction": "z"},
        {"mode": "width", "min_distance": 1, "min_contrast": 0},
        {"mode": "presence", "min_count": 3, "max_count": 1},
        {"mode": "width", "min_distance": 1, "unknown": 1},
    ),
    passing=BAR,
    failing=FLAT,
    nothing_on_fail="it fails by not finding the edges: there is no line to draw",
    goldens=(
        Golden("a bar of exactly 120 px", BAR, passed=True, values={"distance": 120, "count": 2}, tolerance=0.05, marks=(LINE, LINE2, ("text", "found", (79.5, 12, 79.5, 12)))),
        Golden("the same bar, blurred (sigma 2)", cv2.GaussianBlur(BAR, (0, 0), 2), {"sigma": 2.0}, passed=True, values={"distance": 120}, tolerance=0.2),
        Golden("a step between pixels, at 50.3", STEP, {"mode": "position", "min_distance": 0, "max_distance": 100}, passed=True, values={"distance": 50.3}, tolerance=0.05),
        Golden("the first edge of the bar is at 20", BAR, {"mode": "position", "min_distance": 19, "max_distance": 21}, passed=True, values={"distance": 20.0}, tolerance=0.05, marks=(LINE,)),
        Golden("the bar scanned from top to bottom", BAR.T.copy(), {"direction": "y"}, passed=True, values={"distance": 120}, tolerance=0.05,
               marks=(("poly", "found", (0, 19.5, 39, 19.5)), ("poly", "found", (0, 139.5, 39, 139.5)), ("text", "found", (2, 79.5, 2, 79.5)))),
        Golden("a dark bar on a light region is as wide", strip((20, 140), low=HIGH, high=LOW), passed=True, values={"distance": 120}, tolerance=0.05),
        Golden("a width too wide is the defect", BAR, {"max_distance": 100}, passed=False, values={"distance": 120}, tolerance=0.05, marks=(("poly", "defect", LINE[2]), ("poly", "defect", LINE2[2]), ("text", "defect", (79.5, 12, 79.5, 12)))),
        Golden("two edges of any polarity", BAR, {"mode": "presence", "min_count": 2, "max_count": 2}, passed=True, values={"count": 2}, tolerance=0, marks=(LINE, LINE2)),
        Golden("only the rising edges", BAR, {"mode": "presence", "polarity": "rising", "min_count": 1, "max_count": 1}, passed=True, values={"count": 1}, tolerance=0, marks=(LINE,)),
        Golden("only the falling edges", BAR, {"mode": "presence", "polarity": "falling", "min_count": 1, "max_count": 1}, passed=True, values={"count": 1}, tolerance=0, marks=(LINE2,)),
        Golden("a step too faint to count", strip((20, 140), low=100, high=110), {"mode": "presence", "min_count": 1}, passed=False, values={"count": 0}, tolerance=0),
        Golden("a comb with a pitch of 20", COMB, {"mode": "pitch", "min_distance": 15, "max_distance": 25}, passed=True,
               values={"distance": 20, "distance_min": 20, "distance_max": 20, "count": 10}, tolerance=0.05),
        Golden("a comb with a tooth missing: the largest gap fails, though the mean is inside", COMB_GAP, {"mode": "pitch", "min_distance": 15, "max_distance": 30}, passed=False,
               values={"distance": 25, "distance_min": 20, "distance_max": 40}, tolerance=0.05),
        Golden("no edge, a position never made up", FLAT, {"mode": "position", "min_distance": None, "max_distance": 500}, passed=False, values={"count": 0}, tolerance=0, marks=()),
        Golden("no pair, a width never made up", FLAT, {"max_distance": 500, "min_distance": None}, passed=False, values={"count": 0}, tolerance=0, marks=()),
        Golden("one edge is not a pair", strip((100, 200)), {"max_distance": 500, "min_distance": None}, passed=False, values={"count": 1}, tolerance=0),
        Golden("a pitch needs two edges", strip((100, 120)), {"mode": "pitch", "max_distance": 500, "min_distance": None}, passed=False, values={"count": 2}, tolerance=0),
        Golden("a light disc of diameter 80", DISC, {"mode": "diameter", "polarity": "falling", "min_distance": 70, "max_distance": 90}, passed=True,
               values={"distance": 80, "roundness": 0}, tolerance=0.3, marks=(("poly", "found", (19.5, 19.5, 99.5, 99.5)), ("point", "found", (59.5, 59.5, 59.5, 59.5)), ("text", "found", (59.5, 59.5, 59.5, 59.5)))),
        Golden("a dark hole in a light plate", 240 - DISC, {"mode": "diameter", "polarity": "rising", "min_distance": 70, "max_distance": 90}, passed=True, values={"distance": 80}, tolerance=0.3),
        Golden("a disc off the centre of its region", DISC_OFF, {"mode": "diameter", "polarity": "falling", "min_distance": 50, "max_distance": 70}, passed=True, values={"distance": 60}, tolerance=0.3),
        Golden("a disc too large", DISC, {"mode": "diameter", "polarity": "falling", "max_distance": 70}, passed=False, values={"distance": 80}, tolerance=0.3,
               marks=(("poly", "defect", (19.5, 19.5, 99.5, 99.5)), ("point", "defect", (59.5, 59.5, 59.5, 59.5)), ("text", "defect", (59.5, 59.5, 59.5, 59.5)))),
        Golden("no disc, no diameter made up", np.full((120, 120), 100, np.uint8), {"mode": "diameter", "max_distance": 500, "min_distance": None}, passed=False, values={"count": 0}, tolerance=0, marks=()),
        Golden("a stripe is no circle", np.tile(strip((40, 80))[0, :120], (120, 1)), {"mode": "diameter", "max_distance": 500, "min_distance": None}, passed=False, tolerance=0),
        Golden("the diameter in millimetres of a calibrated job", DISC, {"mode": "diameter", "polarity": "falling", "min_distance": None, "max_distance": None, "min_distance_mm": 35, "max_distance_mm": 45}, HALF_MM,
               passed=True, values={"distance": 80, "distance_mm": 40}, tolerance=0.3),
        Golden("the width in millimetres of a calibrated job", BAR, {"min_distance": None, "max_distance": None, "min_distance_mm": 55, "max_distance_mm": 65}, HALF_MM,
               passed=True, values={"distance": 120, "distance_mm": 60}, tolerance=0.05),
        Golden("the width in millimetres, too narrow", BAR, {"min_distance": None, "max_distance": None, "min_distance_mm": 70}, HALF_MM, passed=False, values={"distance_mm": 60}, tolerance=0.05),
    ),
)}
