import cv2

from validation.case import Case, Golden, Scene
from validation.scenes import bench

_FRAME, _RECT = bench(printed=True)
_H, _W = _FRAME.shape[:2]
_X0, _Y0, _X1, _Y1 = (round(v * n) for v, n in zip(_RECT, (_W, _H, _W, _H)))
_AWAY = bench(printed=True, at=(60, 300))

LOCATORS = {1: Case(
    params={"template": "t.png"},
    files={"t.png": cv2.imencode(".png", _FRAME[_Y0:_Y1, _X0:_X1])[1].tobytes()},
    bad_params=(
        {},
        {"template": ""},
        {"template": "t.png", "search": [0.9, 0, 0.1, 1]},
        {"template": "t.png", "min_score": 0},
        {"template": "t.png", "angles": [10, -10]},
        {"template": "t.png", "angles": [-200, 20]},
        {"template": "t.png", "scales": [0, 1.1]},
        {"template": "t.png", "scales": [1.2, 0.9]},
        {"template": "t.png", "polarity": "mixed"},
        {"template": "t.png", "unknown": 1},
    ),
    scene=Scene(_FRAME, _RECT),
    goldens=(
        Golden("the part away from the centre", _AWAY[0], rect=_AWAY[1], tolerance=2 / 640),
        Golden("the part, but looked for in the other half of the frame", _AWAY[0], {"search": [0.5, 0.0, 1.0, 1.0]}),
        Golden("an empty bench", bench(printed=True, at=(-1, -1))[0]),
    ),
)}
