import numpy as np

from validation.case import Case, Golden


def flat(level, shape=(40, 40)):
    return np.full(shape, level, np.uint8)


def split(left=0, right=255):
    image = np.full((100, 100), left, np.uint8)
    image[:, 50:] = right
    return image


def glare():
    image = np.full((100, 100), 100, np.uint8)
    image[:10] = 250  # a tenth of the region
    return image


RAMP = np.tile(np.arange(256, dtype=np.uint8), (20, 1))

TOOLS = {1: Case(
    params={"min_mean": 100, "max_mean": 160},
    bad_params=(
        {},  # no criterion to judge by
        {"min_mean": 200, "max_mean": 100},
        {"min_mean": 300},
        {"max_std": -1},
        {"level": 300, "max_above": 0.5},
        {"max_above": 2},
        {"min_mean": 100, "unknown": 1},
    ),
    passing=flat(128),
    failing=flat(20),
    draws_nothing="it measures the whole region, whose outline is its drawing",
    goldens=(
        Golden("a flat region at 128", flat(128), passed=True, values={"mean": 128, "std": 0, "min": 128, "max": 128}, tolerance=0.5),
        Golden("a flat region at 128, 200 asked", flat(128), {"min_mean": 200, "max_mean": 255}, passed=False, values={"mean": 128}, tolerance=0.5),
        Golden("half black, half white", split(), {"min_mean": 0, "max_std": 50, "level": 128}, passed=False,
               values={"mean": 127.5, "std": 127.5, "above": 0.5, "below": 0.5}, tolerance=0.5),
        Golden("half black, half white: even enough", split(100, 140), {"min_mean": 0, "max_std": 50}, passed=True, values={"std": 20}, tolerance=0.5),
        Golden("a tenth of the region is glare", glare(), {"min_mean": 0, "level": 200, "max_above": 0.05}, passed=False, values={"above": 0.10, "below": 0.90}, tolerance=0.001),
        Golden("a tenth of the region is glare, 15 % allowed", glare(), {"min_mean": 0, "level": 200, "max_above": 0.15}, passed=True, values={"above": 0.10}, tolerance=0.001),
        Golden("a ramp from 0 to 255", RAMP, {"min_mean": 0}, passed=True, values={"mean": 127.5, "std": 73.9, "min": 0, "max": 255}, tolerance=0.1),
    ),
)}
