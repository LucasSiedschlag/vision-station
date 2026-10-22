"""The calibration of a job: millimetres per pixel (FR-INS-15, architecture §14.4).

It is a file of the job (`camera/calibration.yaml`) because the scale depends on the zoom, the focus and the distance, which
are the job's. A tool that measures in millimetres reads it through `JobFiles.scale()`; a job that uses millimetres with
no calibration is refused when it is loaded.
"""

from dataclasses import dataclass
from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

CALIBRATION_FILE = "camera/calibration.yaml"

Positive = Annotated[float, Field(gt=0, allow_inf_nan=False)]


@dataclass(frozen=True)
class Scale:
    """Millimetres per pixel along x and along y (equal unless the pixels are not square)."""

    x: float
    y: float

    @property
    def mean(self) -> float:
        return (self.x + self.y) / 2


class Calibration(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method: Literal["known_dimension"]  # `checkerboard` (with lens distortion) is not built
    mm_per_px: Positive | tuple[Positive, Positive]  # one value, or x and y
    date: date
    residual_mm: Annotated[float, Field(ge=0, allow_inf_nan=False)] | None = None  # the worst miss of the known dimensions used

    @property
    def scale(self) -> Scale:
        x, y = (self.mm_per_px, self.mm_per_px) if isinstance(self.mm_per_px, float | int) else self.mm_per_px
        return Scale(float(x), float(y))
