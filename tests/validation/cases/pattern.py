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


TOOLS = {1: Case(
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
)}
