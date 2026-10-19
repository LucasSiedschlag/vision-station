"""Writes frontend/src/test/hsv-parity.json: what OpenCV says of a grid of colours, for the interface's own HSV code to match.

The editor draws the mask of a colour range and reads the colour under the pointer in the browser (document 05 §19.4),
so it must agree with `vision_station.algorithms.color.color_mask`. Run again if the colour code changes:
    uv run python scripts/make_hsv_fixture.py
"""

import json
from itertools import product
from pathlib import Path

import cv2
import numpy as np

from vision_station.algorithms.color import ColorRange, color_mask

OUT = Path(__file__).resolve().parents[1] / "frontend" / "src" / "test" / "hsv-parity.json"
LEVELS = [0, 1, 37, 64, 100, 128, 150, 191, 222, 254, 255]
RANGES = [
    {"hue": [100, 125], "s_min": 120, "s_max": 255, "v_min": 70, "v_max": 255},
    {"hue": [170, 10], "s_min": 90, "s_max": 255, "v_min": 60, "v_max": 255},  # through red
    {"hue": None, "s_min": 0, "s_max": 40, "v_min": 200, "v_max": 255},  # whites
    {"hue": [20, 35], "s_min": 50, "s_max": 200, "v_min": 0, "v_max": 180},
]


def main() -> None:
    rgb = np.array(list(product(LEVELS, repeat=3)), np.uint8)
    bgr = rgb[:, ::-1].reshape(-1, 1, 3)
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV).reshape(-1, 3)
    masks = [color_mask(bgr, ColorRange(**r)).reshape(-1) for r in RANGES]
    out = {
        "colours": rgb.tolist(),
        "hsv": hsv.tolist(),
        "ranges": [{**r, "inside": m.astype(int).tolist()} for r, m in zip(RANGES, masks)],
    }
    OUT.write_text(json.dumps(out, separators=(",", ":")))
    print(f"{len(rgb)} colours, {len(RANGES)} ranges -> {OUT}")


if __name__ == "__main__":
    main()
