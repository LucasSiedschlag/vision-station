"""Blob locator: the object is the largest region of a color, or darker or lighter than the background.

For objects that stand out from what is around them: a box on a light bench, a colored part, a dark
label. The anchor is the upright rectangle around the largest region whose area is between `min_area` and
`max_area` (fractions of the search area). Its score is how much of that rectangle the region fills, so a
square part gives about 1 and a rotated one less; the score is reported, not used to reject.
"""

from typing import Annotated, Literal, Self

import cv2
import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

from vision_station.colors import ColorRange, color_mask
from vision_station.jobfiles import JobFiles
from vision_station.locators.base import Anchor, LocatorType, register

Fraction = Annotated[float, Field(ge=0, le=1)]


class BlobParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["color", "dark", "light"]
    color: ColorRange | None = None  # for mode 'color'
    threshold: Annotated[int, Field(ge=0, le=255)] | None = None  # gray level for 'dark'/'light'; None = automatic (Otsu)
    search: tuple[Fraction, Fraction, Fraction, Fraction] = (0.0, 0.0, 1.0, 1.0)
    min_area: Annotated[float, Field(gt=0, le=1)] = 0.02
    max_area: Annotated[float, Field(gt=0, le=1)] = 1.0
    clean_px: Annotated[int, Field(ge=0, le=50)] = 3  # removes specks and fills small holes, at work size
    work_width: Annotated[int, Field(ge=64, le=4096)] = 640

    @model_validator(mode="after")
    def _valid(self) -> Self:
        x0, y0, x1, y1 = self.search
        if not (x0 < x1 and y0 < y1):
            raise ValueError("search must be [x0, y0, x1, y1] with x0 < x1 and y0 < y1")
        if self.mode == "color" and self.color is None:
            raise ValueError("mode 'color' needs color")
        if self.min_area > self.max_area:
            raise ValueError("min_area must not be above max_area")
        return self


def _mask(area: np.ndarray, params: BlobParams) -> np.ndarray:
    if params.mode == "color":
        return color_mask(area, params.color).astype(np.uint8) * 255  # type: ignore[arg-type]
    gray = cv2.cvtColor(area, cv2.COLOR_BGR2GRAY) if area.ndim == 3 else area
    kind = cv2.THRESH_BINARY_INV if params.mode == "dark" else cv2.THRESH_BINARY
    if params.threshold is None:
        _, mask = cv2.threshold(gray, 0, 255, kind | cv2.THRESH_OTSU)
    else:
        _, mask = cv2.threshold(gray, params.threshold, 255, kind)
    return mask


def locate(frame: np.ndarray, params: BlobParams, files: JobFiles) -> Anchor | None:
    height, width = frame.shape[:2]
    sx0, sy0, sx1, sy1 = (round(v * n) for v, n in zip(params.search, (width, height, width, height)))
    area = frame[sy0:sy1, sx0:sx1]
    if area.size == 0:
        return None
    scale = min(1.0, params.work_width / width)
    if scale < 1.0:
        area = cv2.resize(area, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    mask = _mask(area, params)
    if params.clean_px:
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (params.clean_px, params.clean_px))
        mask = cv2.morphologyEx(cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel), cv2.MORPH_CLOSE, kernel)
    count, _, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    total = mask.shape[0] * mask.shape[1]
    best = None
    for i in range(1, count):
        x, y, w, h, a = stats[i]
        if params.min_area * total <= a <= params.max_area * total and (best is None or a > best[4]):
            best = (x, y, w, h, a)
    if best is None:
        return None
    x, y, w, h, a = best
    rect = ((sx0 + x / scale) / width, (sy0 + y / scale) / height, min(1.0, (sx0 + (x + w) / scale) / width), min(1.0, (sy0 + (y + h) / scale) / height))
    return Anchor(rect=rect, score=float(a / (w * h)))


BLOB = register(LocatorType(name="blob", version=1, params=BlobParams, locate=locate))
