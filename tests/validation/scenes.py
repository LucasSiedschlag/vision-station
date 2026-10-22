"""Neutral pictures for the locators' cases: a dark part with a printed pattern on a light bench."""

import cv2
import numpy as np

BENCH, PART = (205, 205, 200), (70, 70, 75)  # BGR
SIZE = (480, 640)  # rows, columns


def texture(h=90, w=160, seed=3):
    rng = np.random.default_rng(seed)
    blocks = rng.integers(0, 2, (h // 10, w // 10), dtype=np.uint8)
    tex = np.kron(blocks, np.ones((10, 10), np.uint8))
    img = np.full((h, w, 3), PART, np.uint8)
    img[tex == 1] = (150, 150, 150)
    return img


def bench(printed: bool, h=90, w=160, at: tuple[int, int] | None = None):
    """The bench with the part (top-left `at`, default the centre); `printed` or plain dark. Returns the frame and the
    part's box (fractions); with `at=(-1, -1)` the bench is empty."""
    frame = np.full((*SIZE, 3), BENCH, np.uint8)
    x, y = at or ((SIZE[1] - w) // 2, (SIZE[0] - h) // 2)
    if at != (-1, -1):
        frame[y : y + h, x : x + w] = texture(h, w) if printed else PART
    return frame, (x / SIZE[1], y / SIZE[0], (x + w) / SIZE[1], (y + h) / SIZE[0])
