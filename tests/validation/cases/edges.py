from validation.case import Case, Golden, Scene
from validation.scenes import bench

# the bench: a dark part of 160 x 90 px on a light bench of 640 x 480; the corner is its top-left one
_FRAME, _RECT = bench(printed=False)
_W, _H = 640, 480
_X0, _Y0, _X1, _Y1 = _RECT
CORNER = (_X0, _Y0)


def box(x0, y0, x1, y1):
    return [x0 / _W, y0 / _H, x1 / _W, y1 / _H]


# windows along the two edges, shorter than them (a part turned by 10° stays inside), a hundred pixels wide across the edge
VERTICAL = {"rect": box(200, 225, 300, 280), "polarity": "falling"}  # the left edge, light to dark going right
HORIZONTAL = {"rect": box(280, 150, 380, 240), "polarity": "falling"}  # the top edge, light to dark going down
PARAMS = {"vertical": VERTICAL, "horizontal": HORIZONTAL, "taught_rect": list(_RECT), "taught_corner": list(CORNER)}


def _scene(dx, dy):
    frame, rect = bench(printed=False, at=(240 + dx, 195 + dy))
    return frame, rect


LOCATORS = {1: Case(
    params=PARAMS,
    bad_params=(
        {},
        {**PARAMS, "vertical": {**VERTICAL, "rect": [0.5, 0.1, 0.2, 0.9]}},  # x0 above x1
        {**PARAMS, "vertical": {**VERTICAL, "polarity": "any"}},
        {**PARAMS, "horizontal": {**HORIZONTAL, "bands": 1}},
        {**PARAMS, "taught_rect": [0.6, 0.1, 0.2, 0.9]},
        {**PARAMS, "taught_corner": [1.5, 0.1]},
        {**PARAMS, "unknown": 1},
    ),
    scene=Scene(_FRAME, _RECT),
    goldens=(
        Golden("the part a few pixels to the right and down", _scene(12, 9)[0], rect=_scene(12, 9)[1], tolerance=1.5 / 640),
        Golden("the part a little to the left", _scene(-15, 0)[0], rect=_scene(-15, 0)[1], tolerance=1.5 / 640),
        Golden("an empty bench", bench(printed=False, at=(-1, -1))[0]),
    ),
)}
