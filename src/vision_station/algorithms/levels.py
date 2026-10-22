"""Gray levels of a region: the statistics and the share of pixels beyond a level (pure functions)."""

import cv2
import numpy as np


def gray_of(image: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image


def level_stats(image: np.ndarray) -> dict[str, float]:
    """Mean, standard deviation, minimum and maximum of the gray level, 0 to 255. The image must not be empty."""
    gray = gray_of(image)
    mean, std = cv2.meanStdDev(gray)
    return {"mean": float(mean[0, 0]), "std": float(std[0, 0]), "min": float(gray.min()), "max": float(gray.max())}


def share_beyond(image: np.ndarray, level: int) -> tuple[float, float]:
    """The fraction of pixels above `level` and the fraction below it (the ones equal to it are in neither)."""
    gray = gray_of(image)
    return float((gray > level).mean()), float((gray < level).mean())
