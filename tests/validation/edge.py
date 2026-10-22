"""Inputs for V3 (architecture §15.3): what a camera, a bad crop or a broken job can hand a tool."""

import numpy as np


def edge_inputs() -> dict[str, np.ndarray]:
    rng = np.random.default_rng(7)
    return {
        "empty": np.zeros((0, 0, 3), np.uint8),
        "empty-gray": np.zeros((0, 0), np.uint8),
        "1x1": np.full((1, 1, 3), 128, np.uint8),
        "1x1-gray": np.full((1, 1), 128, np.uint8),
        "1-row": rng.integers(0, 256, (1, 200, 3), dtype=np.uint8),
        "8x8-noise": rng.integers(0, 256, (8, 8, 3), dtype=np.uint8),
        "black": np.zeros((64, 64, 3), np.uint8),
        "white": np.full((64, 64, 3), 255, np.uint8),
        "noise": rng.integers(0, 256, (90, 120, 3), dtype=np.uint8),
        "noise-gray": rng.integers(0, 256, (90, 120), dtype=np.uint8),
    }
