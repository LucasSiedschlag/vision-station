"""The scale of a picture from a dimension known in the scene (FR-INS-15): pure functions."""

import math
from collections.abc import Sequence

import numpy as np


def calibrate_known_dimension(pixels: float | Sequence[float], millimetres: float | Sequence[float]) -> tuple[float, float]:
    """Millimetres per pixel from one or more known dimensions measured on the picture, and the worst miss in millimetres.
    With several the scale is the line through the origin that fits them best. Raises `ValueError` on a dimension that
    is not a positive finite number, or lists of different lengths."""
    px = np.atleast_1d(np.asarray(pixels, dtype=float))
    mm = np.atleast_1d(np.asarray(millimetres, dtype=float))
    if px.size == 0 or px.shape != mm.shape or px.ndim != 1:
        raise ValueError("give the same number of dimensions in pixels and in millimetres, at least one")
    if not (np.isfinite(px).all() and np.isfinite(mm).all() and (px > 0).all() and (mm > 0).all()):
        raise ValueError("a known dimension is a positive number, in pixels and in millimetres")
    scale = float(px @ mm / (px @ px))
    residual = float(np.abs(mm - scale * px).max())
    if not math.isfinite(scale) or scale <= 0:
        raise ValueError("the dimensions give no scale")
    return scale, residual
