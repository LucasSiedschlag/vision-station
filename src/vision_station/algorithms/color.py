"""Which pixels have a color: a range in HSV, or a distance to a reference color (CIELAB, ΔE76).

Shared by the `color` tool and the `blob` locator, so a color means the same in both.
"""

from typing import Annotated, Literal, Self

import cv2
import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

from vision_station.core.schema_labels import COLOR_META, COLOR_RANGE, labels

Byte = Annotated[int, Field(ge=0, le=255)]
Hue = Annotated[int, Field(ge=0, le=179)]  # OpenCV hue: degrees / 2


class ColorRange(BaseModel):
    """`range`: hue (lo > hi wraps through red, e.g. [170, 10]), saturation and value limits.
    `reference`: every pixel within `max_distance` (ΔE, CIELAB) of `rgb`."""

    model_config = ConfigDict(extra="forbid", json_schema_extra=labels(meta=COLOR_META, **COLOR_RANGE))

    mode: Literal["range", "reference"] = "range"
    hue: tuple[Hue, Hue] | None = None  # None: any hue (e.g. black or white, by value alone)
    s_min: Byte = 0
    s_max: Byte = 255
    v_min: Byte = 0
    v_max: Byte = 255
    rgb: tuple[Byte, Byte, Byte] | None = None
    max_distance: Annotated[float, Field(gt=0, le=200)] = 20.0

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if self.mode == "reference" and self.rgb is None:
            raise ValueError("mode 'reference' needs rgb")
        if self.s_min > self.s_max or self.v_min > self.v_max:
            raise ValueError("s_min/v_min must not be above s_max/v_max")
        return self


def as_bgr(image: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR) if image.ndim == 2 else image


def color_mask(image: np.ndarray, color: ColorRange) -> np.ndarray:
    """A boolean mask, True where the pixel has the color."""
    bgr = as_bgr(image)
    if color.mode == "reference":
        lab = cv2.cvtColor(bgr.astype(np.float32) / 255.0, cv2.COLOR_BGR2Lab)
        r, g, b = color.rgb  # type: ignore[misc]  (checked by the model)
        ref = cv2.cvtColor(np.array([[[b, g, r]]], np.float32) / 255.0, cv2.COLOR_BGR2Lab)[0, 0]
        return np.linalg.norm(lab - ref, axis=2) <= color.max_distance
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    if color.hue is None or color.hue[0] <= color.hue[1]:
        lo, hi = color.hue if color.hue is not None else (0, 179)
        return cv2.inRange(hsv, (lo, color.s_min, color.v_min), (hi, color.s_max, color.v_max)) > 0
    lo, hi = color.hue  # wraps through red: [lo, 179] or [0, hi]
    upper = cv2.inRange(hsv, (lo, color.s_min, color.v_min), (179, color.s_max, color.v_max))
    lower = cv2.inRange(hsv, (0, color.s_min, color.v_min), (hi, color.s_max, color.v_max))
    return cv2.bitwise_or(upper, lower) > 0
