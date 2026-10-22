from validation.case import Case, Golden, Scene
from validation.scenes import bench

_RECT = [0.2, 0.2, 0.8, 0.8]

LOCATORS = {1: Case(
    params={"rect": _RECT},
    bad_params=({}, {"rect": [0.8, 0.2, 0.2, 0.8]}, {"rect": [0.2, 0.2, 1.5, 0.8]}),
    scene=Scene(bench(printed=False)[0], tuple(_RECT), follows=False),
    goldens=(Golden("a rectangle written in the job", bench(printed=False)[0], {"rect": [0.1, 0.15, 0.5, 0.6]}, rect=(0.1, 0.15, 0.5, 0.6), tolerance=0),),
)}
