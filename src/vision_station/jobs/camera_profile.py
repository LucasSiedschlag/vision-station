"""Driver-independent camera settings stored in a job (architecture §5.2)."""

from typing import Annotated, Literal, Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ManualOrAuto(_Strict):
    """A setting that is either automatic or fixed at a value (never both)."""

    mode: Literal["auto", "manual"]
    value: float | None

    @model_validator(mode="after")
    def _manual_needs_value(self) -> Self:
        if self.mode == "manual" and self.value is None:
            raise ValueError("manual mode needs a value")
        if self.mode == "auto" and self.value is not None:
            raise ValueError("auto mode takes no value")
        return self


Fraction = Annotated[float, Field(ge=0, le=1)]


class AutoOnce(_Strict):
    """How the editor's *Auto uma vez* measures the exposure (FR-ACQ-11, Cognex `AcquireImage` Auto Exposure).

    The exposure is searched until `target_brightness` percent of the pixels of `region` are saturated, without going
    over `max_exposure_us`. The job then runs with the fixed value that was found; nothing follows the light of the
    moment (principles 1 and 2)."""

    target_brightness: Annotated[float, Field(ge=0, le=100)]  # percent of saturated pixels
    max_exposure_us: Annotated[float, Field(ge=100)]
    region: tuple[Fraction, Fraction, Fraction, Fraction] | None  # x0, y0, x1, y1 of the frame; None: all of it

    @model_validator(mode="after")
    def _region_has_area(self) -> Self:
        if self.region is not None:
            x0, y0, x1, y1 = self.region
            if not (x0 < x1 and y0 < y1):
                raise ValueError("region must be [x0, y0, x1, y1] with x0 < x1 and y0 < y1")
        return self


class Exposure(_Strict):
    mode: Literal["auto", "manual"]
    value_us: Annotated[float, Field(gt=0)] | None
    auto_once: AutoOnce  # how *Auto uma vez* measures

    @model_validator(mode="after")
    def _manual_needs_value(self) -> Self:
        if self.mode == "manual" and self.value_us is None:
            raise ValueError("manual exposure needs value_us")
        if self.mode == "auto" and self.value_us is not None:
            raise ValueError("auto exposure takes no value_us")
        return self


class WhiteBalance(_Strict):
    mode: Literal["auto", "manual"]
    kelvin: Annotated[int, Field(gt=0)] | None

    @model_validator(mode="after")
    def _manual_needs_kelvin(self) -> Self:
        if self.mode == "manual" and self.kelvin is None:
            raise ValueError("manual white balance needs kelvin")
        if self.mode == "auto" and self.kelvin is not None:
            raise ValueError("auto white balance takes no kelvin")
        return self


Orientation = Literal["normal", "mirror", "flip", "rotate180"]


class Zoom(_Strict):
    value: float


class CameraProfile(_Strict):
    """Settings applied to the camera on every open, then read back.

    The C920 needs auto modes off before manual values are accepted; that is a
    driver concern (TD-04), not part of this model.
    """

    resolution: tuple[Annotated[int, Field(gt=0)], Annotated[int, Field(gt=0)]]
    pixel_format: Literal["mjpeg", "yuyv"] | None  # UVC only
    exposure: Exposure
    gain: ManualOrAuto
    white_balance: WhiteBalance
    focus: ManualOrAuto
    zoom: Zoom | None  # motorized lens only
    power_line_hz: Literal[50, 60]
    low_light_compensation: bool
    # applied by the program to every frame, not written to the camera (FR-ACQ-10, TD-32); see PROGRAM_SIDE
    orientation: Orientation


# Profile fields the program applies to the frames itself: a driver neither writes nor reads them back, so they are
# not camera settings in a report (FR-ACQ-4)
PROGRAM_SIDE = ("orientation",)


def dump_profile(profile: CameraProfile) -> str:
    """The profile as YAML, in full (FR-JOB-16): every setting is in the file, so a change of a default in the software
    never changes a saved version, and the loader refuses a file with one missing."""
    return yaml.safe_dump(profile.model_dump(mode="json"), sort_keys=False)
