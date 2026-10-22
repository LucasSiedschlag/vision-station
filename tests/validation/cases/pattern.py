import cv2
import numpy as np

from validation.case import Case, Golden


def texture(seed=3, size=(120, 160)):
    rng = np.random.default_rng(seed)
    blocks = rng.integers(0, 2, (size[0] // 10, size[1] // 10), dtype=np.uint8)
    return (np.kron(blocks, np.ones((10, 10), np.uint8)) * 120 + 60).astype(np.uint8)


MARK = texture()[20:60, 30:80]  # a part of the picture that is only there once
PNG = cv2.imencode(".png", MARK)[1].tobytes()

def canvas(*xs):
    """A flat gray strip with the mark pasted at each x."""
    image = np.full((120, 300), 128, np.uint8)
    for x in xs:
        image[40:80, x : x + 50] = MARK
    return image


_V1 = Case(
    params={"template": "t.png"},
    files={"t.png": PNG},
    bad_params=(
        {"template": ""},
        {"template": "t.png", "min_count": 3, "max_count": 1},
        {"template": "t.png", "min_coverage": 0.5},  # coverage needs an axis
        {"template": "t.png", "min_score": 0},
    ),
    passing=texture(),
    failing=np.full((120, 160), 128, np.uint8),
    nothing_on_fail="it fails by not finding the pattern: there is no box to draw",
    goldens=(
        Golden("the mark three times, three asked", canvas(20, 110, 200), {"min_count": 3, "max_count": 3}, passed=True, values={"count": 3, "best": 1.0}, tolerance=0.02,
               marks=(("rect", "found", (20, 40, 70, 80)), ("rect", "found", (110, 40, 160, 80)), ("rect", "found", (200, 40, 250, 80)))),
        Golden("the mark three times, two at most: the boxes are the defect", canvas(20, 110, 200), {"min_count": 1, "max_count": 2}, passed=False, values={"count": 3},
               marks=(("rect", "defect", (20, 40, 70, 80)), ("rect", "defect", (110, 40, 160, 80)), ("rect", "defect", (200, 40, 250, 80)))),
        Golden("the mark twice, three asked", canvas(20, 200), {"min_count": 3}, passed=False, values={"count": 2}, tolerance=0),
        Golden("no mark", canvas(), {"min_count": 1}, passed=False, values={"count": 0}, tolerance=0),
    ),
)

def turned(image, degrees, scale=1.0):
    """The strip turned about its centre (counter-clockwise on the screen) and scaled."""
    h, w = image.shape[:2]
    return cv2.warpAffine(image, cv2.getRotationMatrix2D((w / 2, h / 2), degrees, scale), (w, h), borderValue=128)


def box(x0, y0, x1, y1):
    return (x0, y0, x1, y1)


_V2 = Case(
    params={"template": "t.png"},
    files={"t.png": PNG},
    bad_params=(
        {"template": ""},
        {"template": "t.png", "min_count": 3, "max_count": 1},
        {"template": "t.png", "min_coverage": 0.5},  # coverage needs an axis
        {"template": "t.png", "min_score": 0},
        {"template": "t.png", "angles": [10, -10]},
        {"template": "t.png", "angles": [-200, 20]},
        {"template": "t.png", "scales": [0, 1.1]},
        {"template": "t.png", "scales": [1.2, 0.9]},
        {"template": "t.png", "polarity": "mixed"},
        {"template": "t.png", "max_instances": 0},
        {"template": "t.png", "unknown": 1},
    ),
    passing=texture(),
    failing=np.full((120, 160), 128, np.uint8),
    nothing_on_fail="it fails by not finding the pattern: there is no box to draw",
    goldens=(
        Golden("the mark three times, three asked", canvas(20, 110, 200), {"min_count": 3, "max_count": 3}, passed=True, values={"count": 3, "best": 1.0}, tolerance=0.02,
               marks=(("poly", "found", box(20, 40, 70, 80)), ("poly", "found", box(110, 40, 160, 80)), ("poly", "found", box(200, 40, 250, 80)))),
        Golden("the mark twice, three asked", canvas(20, 200), {"min_count": 3}, passed=False, values={"count": 2}, tolerance=0),
        Golden("no mark", canvas(), {"min_count": 1}, passed=False, values={"count": 0}, tolerance=0, marks=()),
        Golden("the mark three times, two at most: the boxes are the defect", canvas(20, 110, 200), {"min_count": 1, "max_count": 2}, passed=False, values={"count": 3},
               marks=(("poly", "defect", box(20, 40, 70, 80)), ("poly", "defect", box(110, 40, 160, 80)), ("poly", "defect", box(200, 40, 250, 80)))),
        Golden("the strip turned 12 degrees: the marks are still found", turned(canvas(20, 110, 200), 12.0), {"min_count": 3, "max_count": 3, "angles": [-30, 30]}, passed=True, values={"count": 3}, tolerance=0),
        Golden("the strip turned 40 degrees, 20 allowed", turned(canvas(110), 40.0), {"min_count": 1, "angles": [-20, 20]}, passed=False, values={"count": 0}, tolerance=0),
        Golden("the strip 10 % larger", turned(canvas(110), 0.0, 1.1), {"min_count": 1, "scales": [0.9, 1.2]}, passed=True, values={"count": 1}, tolerance=0),
        Golden("the strip 30 % larger, 10 % allowed", turned(canvas(110), 0.0, 1.3), {"min_count": 1, "scales": [0.9, 1.1]}, passed=False, values={"count": 0}, tolerance=0),
        Golden("light and dark swapped: found only when asked", np.where(canvas(110) == 128, 128, 255 - canvas(110)).astype(np.uint8), {"min_count": 1, "polarity": "ignore"}, passed=True, values={"count": 1}, tolerance=0),
        Golden("light and dark swapped, not asked", np.where(canvas(110) == 128, 128, 255 - canvas(110)).astype(np.uint8), {"min_count": 1}, passed=False, values={"count": 0}, tolerance=0),
        Golden("the whole length covered", canvas(0, 50, 100, 150, 200, 250), {"axis": "x", "min_coverage": 0.95, "max_gap": 0.05}, passed=True, values={"coverage": 1.0, "gap": 0.0}, tolerance=0.02),
        Golden("a stretch without the mark", canvas(0, 50, 100, 250), {"axis": "x", "max_gap": 0.2}, passed=False, values={"coverage": 0.667, "gap": 0.333}, tolerance=0.02),
    ),
)

TOOLS = {1: _V1, 2: _V2}
