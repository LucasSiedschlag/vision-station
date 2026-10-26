"""Writes frontend/src/test/gray-parity.json: what OpenCV says of gray levels and of Otsu's threshold, for the interface's own code to match.

The editor draws the gray histogram of a region and the level the automatic threshold of the `blob` tool will use
(document 05 §19.5), so it must agree with `vision_station.algorithms.blobs.binary_mask`. Run again if that changes:
    uv run python scripts/make_gray_fixture.py
"""

import json
from itertools import product
from pathlib import Path

import cv2
import numpy as np

OUT = Path(__file__).resolve().parents[1] / "frontend" / "src" / "test" / "gray-parity.json"
LEVELS = [0, 1, 37, 64, 100, 128, 150, 191, 222, 254, 255]


def _histograms() -> list[np.ndarray]:
    rng = np.random.default_rng(3)
    two = lambda a, b, n=4000, sa=12, sb=15: np.concatenate([rng.normal(a, sa, n), rng.normal(b, sb, n)])  # noqa: E731
    cases = [
        two(60, 190),
        two(30, 70, sa=5, sb=8),
        two(180, 230, n=500),
        rng.normal(128, 40, 8000),
        rng.uniform(0, 256, 8000),
        np.full(500, 90.0),  # flat: no object
        np.array([0.0] * 300 + [255.0] * 300),  # two levels only
        np.array([10.0, 11.0, 200.0]),  # tiny
        two(5, 250, sa=3, sb=3),
    ]
    return [np.bincount(np.clip(np.round(c), 0, 255).astype(np.uint8), minlength=256) for c in cases]


def main() -> None:
    rgb = np.array(list(product(LEVELS, repeat=3)), np.uint8)
    gray = cv2.cvtColor(rgb[:, ::-1].reshape(-1, 1, 3), cv2.COLOR_BGR2GRAY).reshape(-1)
    otsu = []
    for counts in _histograms():
        pixels = np.repeat(np.arange(256, dtype=np.uint8), counts).reshape(-1, 1)
        level, _ = cv2.threshold(pixels, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
        otsu.append({"counts": counts.tolist(), "level": int(level)})
    OUT.write_text(json.dumps({"colours": rgb.tolist(), "gray": gray.tolist(), "otsu": otsu}, separators=(",", ":")))
    print(f"{len(rgb)} colours, {len(otsu)} histograms -> {OUT}")


if __name__ == "__main__":
    main()
