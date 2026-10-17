"""Image measures used to compare the live view with a job's reference image (architecture §7.3)."""

import cv2
import numpy as np

_SHARPNESS_WIDTH = 640  # measured at a fixed width, so cameras of different resolution compare
_THUMB = (96, 54)


def _gray(image: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image


def brightness(image: np.ndarray) -> float:
    """Mean gray level, 0..255."""
    return float(_gray(image).mean())


def sharpness(image: np.ndarray) -> float:
    """Variance of the Laplacian at a fixed width: higher is sharper. Only meaningful against another
    measure of the same scene."""
    gray = _gray(image)
    h, w = gray.shape
    if w != _SHARPNESS_WIDTH:
        gray = cv2.resize(gray, (_SHARPNESS_WIDTH, max(1, round(h * _SHARPNESS_WIDTH / w))), interpolation=cv2.INTER_AREA)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def similarity(a: np.ndarray, b: np.ndarray) -> float:
    """How alike two views are, 0..1: zero-mean correlation of small blurred copies.

    Insensitive to overall brightness (brightness is checked on its own) and to small shifts, but a
    moved camera, a different scene or a lost focus lower it.
    """
    ta, tb = (cv2.GaussianBlur(cv2.resize(_gray(x), _THUMB, interpolation=cv2.INTER_AREA), (3, 3), 0).astype(np.float64) for x in (a, b))
    ta, tb = ta - ta.mean(), tb - tb.mean()
    denom = np.sqrt((ta**2).sum() * (tb**2).sum())
    if denom < 1e-9:
        return 1.0 if np.allclose(ta, tb) else 0.0
    return float(max(0.0, (ta * tb).sum() / denom))
