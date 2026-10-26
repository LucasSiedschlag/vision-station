"""`color_mask` must give the same mask as the plain per-channel comparison it replaced (speed only, no change of result)."""

import cv2
import numpy as np
import pytest

from vision_station.algorithms.color import ColorRange, as_bgr, color_mask


def _by_comparison(image: np.ndarray, color: ColorRange) -> np.ndarray:
    hsv = cv2.cvtColor(as_bgr(image), cv2.COLOR_BGR2HSV)
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    mask = (s >= color.s_min) & (s <= color.s_max) & (v >= color.v_min) & (v <= color.v_max)
    if color.hue is not None:
        lo, hi = color.hue
        mask &= ((h >= lo) & (h <= hi)) if lo <= hi else ((h >= lo) | (h <= hi))
    return mask


@pytest.mark.parametrize(
    "color",
    [
        ColorRange(),
        ColorRange(hue=(86, 105), s_min=30),
        ColorRange(hue=(170, 8), s_min=120),  # wraps through red
        ColorRange(hue=(0, 179)),
        ColorRange(hue=(10, 10), s_min=5, s_max=250, v_min=7, v_max=200),
        ColorRange(s_max=40, v_min=180),  # white, by saturation and value alone
        ColorRange(hue=(179, 0)),
    ],
)
def test_same_mask_as_comparison(color):
    rng = np.random.default_rng(7)
    image = rng.integers(0, 256, (120, 160, 3), dtype=np.uint8)
    mask = color_mask(image, color)
    assert mask.dtype == bool and mask.shape == image.shape[:2]
    assert np.array_equal(mask, _by_comparison(image, color))


def test_gray_image_is_accepted():
    gray = np.arange(256, dtype=np.uint8).reshape(16, 16)
    color = ColorRange(v_min=100, v_max=200)
    assert np.array_equal(color_mask(gray, color), _by_comparison(gray, color))
