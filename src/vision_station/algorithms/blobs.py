"""Blobs: the binary mask of a region and its connected parts (pure functions).

Shared by the `blob` locator and the `blob` tool, so a blob means the same in both.
"""

from typing import Literal

import cv2
import numpy as np

from vision_station.algorithms.color import ColorRange, color_mask


def binary_mask(
    area: np.ndarray, mode: Literal["color", "dark", "light"], color: ColorRange | None, threshold: int | None, min_contrast: int = 0
) -> np.ndarray:
    """The pixels that are the object, 255, as a `uint8` picture: those of a colour, or darker or lighter than a gray level
    (`threshold`; None: the one Otsu's method finds, which on a region that is all one level just splits its noise: with a
    `min_contrast` above 0, a region whose levels span less than that has no object)."""
    if mode == "color":
        return color_mask(area, color).astype(np.uint8) * 255  # type: ignore[arg-type]
    gray = cv2.cvtColor(area, cv2.COLOR_BGR2GRAY) if area.ndim == 3 else area
    kind = cv2.THRESH_BINARY_INV if mode == "dark" else cv2.THRESH_BINARY
    if threshold is None:
        if min_contrast and int(gray.max()) - int(gray.min()) < min_contrast:
            return np.zeros_like(gray)
        _, mask = cv2.threshold(gray, 0, 255, kind | cv2.THRESH_OTSU)
    else:
        _, mask = cv2.threshold(gray, threshold, 255, kind)
    return mask


def clean_mask(mask: np.ndarray, size: int) -> np.ndarray:
    """Removes specks and closes small holes with an ellipse `size` pixels wide; 0 leaves the mask as it is."""
    if not size:
        return mask
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (size, size))
    return cv2.morphologyEx(cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel), cv2.MORPH_CLOSE, kernel)


def components(mask: np.ndarray) -> tuple[int, np.ndarray, np.ndarray]:
    """The 8-connected parts of a mask: how many labels there are (0 is the background), the label of each pixel, and the
    statistics of each (left, top, width, height, area)."""
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    return count, labels, stats
