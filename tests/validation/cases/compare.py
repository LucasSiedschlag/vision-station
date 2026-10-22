import numpy as np
import yaml

from test_variation import GOOD, defect, sample
from validation.case import Case, Golden
from vision_station.algorithms.variation import teach
from vision_station.core.calibration import CALIBRATION_FILE

MODEL = {"models/m.var": teach(GOOD)}
HALF_MM = {**MODEL, CALIBRATION_FILE: yaml.safe_dump({"method": "known_dimension", "mm_per_px": 0.5, "date": "2026-10-22"}).encode()}  # 144 px = 36 mm²
LIMIT = {"max_area": 30}


def two():
    return defect(defect(sample(510), x=20, y=20), x=110, y=80)


def box(x, y, size=12):
    return (x, y, x + size - 1, y + size - 1)


TOOLS = {1: Case(
    params={"model": "models/m.var", **LIMIT},
    files=MODEL,
    bad_params=(
        {},
        {"model": "models/m.var"},  # no limit to judge by
        {"model": "", "max_area": 1},
        {"model": "models/m.var", "max_area": -1},
        {"model": "models/m.var", "max_area": 1, "abs_threshold": 0},
        {"model": "models/m.var", "max_area": 1, "k": -1},
        {"model": "models/m.var", "max_area": 1, "clean_px": 99},
        {"model": "models/m.var", "max_area": 1, "unknown": 1},
    ),
    passing=sample(500),
    failing=defect(sample(501)),
    goldens=(
        Golden("a part like the good ones", sample(500), passed=True, values={"count": 0, "area": 0}, tolerance=0, marks=()),
        Golden("a bright defect of 12 x 12", defect(sample(501), x=50, y=30), passed=False, values={"count": 1, "area": 144}, tolerance=10, marks=(("poly", "defect", box(50, 30)),)),
        Golden("a dark defect of 12 x 12", defect(sample(502), x=50, y=30, plus=-80), passed=False, values={"count": 1, "area": 144}, tolerance=10, marks=(("poly", "defect", box(50, 30)),)),
        Golden("two defects", two(), {"max_area": 5000, "max_count": 1}, passed=False, values={"count": 2, "area": 288}, tolerance=20,
               marks=(("poly", "defect", box(20, 20)), ("poly", "defect", box(110, 80)))),
        Golden("two defects, two allowed", two(), {"max_area": 5000, "max_count": 2}, passed=True, values={"count": 2}, tolerance=0,
               marks=(("poly", "found", box(20, 20)), ("poly", "found", box(110, 80)))),
        Golden("the largest defect is limited", defect(sample(503), x=50, y=30), {"max_area": 5000, "max_largest": 100}, passed=False, values={"largest": 144}, tolerance=10),
        Golden("a defect under the filter is ignored", defect(sample(504), x=50, y=30, size=3), {"max_area": 0}, passed=True, values={"count": 0}, tolerance=0, marks=()),
        Golden("the same defect when the filter lets it count", defect(sample(504), x=50, y=30, size=3), {"max_area": 0, "filter_min": 1}, passed=False, values={"count": 1}, tolerance=0),
        Golden("a good part moved by (4, -3) is registered", sample(505, shift=(4, -3)), passed=True, values={"area": 0}, tolerance=0),
        Golden("a defect on a part moved by (4, -3) is still found", defect(sample(506, shift=(4, -3)), x=60, y=50), passed=False, values={"count": 1, "area": 144}, tolerance=15),
        Golden("a good part with more noise", sample(507, noise=4.0), passed=True, values={"area": 0}, tolerance=0),
        Golden("15 % darker is the same part", np.clip(sample(508) * 0.85, 0, 255).astype(np.uint8), passed=True, values={"area": 0, "gain": 0.85}, tolerance=0.03),
        Golden("15 % brighter is the same part", np.clip(sample(509) * 1.15, 0, 255).astype(np.uint8), passed=True, values={"area": 0, "gain": 1.15}, tolerance=0.03),
        Golden("40 % darker is not", (sample(510) * 0.6).astype(np.uint8), {"max_area": 100}, passed=False, values={"gain": 0.8}, tolerance=0.03),
        Golden("the defect in square millimetres of a calibrated job", defect(sample(511), x=50, y=30), {"max_area": None, "max_largest_mm2": 30}, HALF_MM, passed=False,
               values={"largest": 144, "largest_mm2": 36}, tolerance=10),
        Golden("a calibrated job reports both areas", sample(512), {"max_area": 30}, HALF_MM, passed=True, values={"area": 0, "area_mm2": 0}, tolerance=0),
    ),
)}
