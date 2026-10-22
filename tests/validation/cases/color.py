import numpy as np

from validation.case import Case, Golden

BLUE, RED = (200, 90, 30), (30, 30, 220)  # BGR


def patch(colour):
    return np.full((40, 40, 3), colour, np.uint8)


def stripes(*spans):
    """100 x 100 gray with full-height blue columns at each (from, to)."""
    image = np.full((100, 100, 3), 128, np.uint8)
    for a, b in spans:
        image[:, a:b] = BLUE
    return image


_30 = stripes((0, 30))

TOOLS = {1: Case(
    params={"hue": [100, 130], "s_min": 60, "min_fraction": 0.5},
    bad_params=(
        {"hue": [100, 130]},  # no criterion to judge by
        {"hue": [100, 130], "min_fraction": 0.8, "max_fraction": 0.2},
        {"hue": [100, 130], "min_coverage": 0.5},  # coverage needs an axis
        {"hue": [100, 300], "min_fraction": 0.5},
        {"mode": "reference", "min_fraction": 0.5},  # needs rgb
    ),
    passing=patch(BLUE),
    failing=patch(RED),
    goldens=(
        Golden("30 % of the area, inside 25..35 %", _30, {"min_fraction": 0.25, "max_fraction": 0.35}, passed=True, values={"fraction": 0.30}),
        Golden("30 % of the area, 50 % asked", _30, {"min_fraction": 0.5}, passed=False, values={"fraction": 0.30}),
        Golden("a 40 % gap in the middle", stripes((0, 20), (60, 100)), {"min_fraction": 0.1, "axis": "x", "max_gap": 0.3}, passed=False, values={"coverage": 0.6, "gap": 0.4}),
    ),
)}
