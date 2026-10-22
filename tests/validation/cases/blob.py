from validation.case import Case, Golden, Scene
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
