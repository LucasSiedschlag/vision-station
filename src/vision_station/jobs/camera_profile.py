"""Driver-independent camera settings stored in a job (architecture §5.2)."""

from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ManualOrAuto(_Strict):
    """A setting that is either automatic or fixed at a value (never both)."""

    mode: Literal["auto", "manual"]
    value: float | None = None

    @model_validator(mode="after")
    def _manual_needs_value(self) -> Self:
        if self.mode == "manual" and self.value is None:
            raise ValueError("manual mode needs a value")
        if self.mode == "auto" and self.value is not None:
            raise ValueError("auto mode takes no value")
        return self


class Exposure(_Strict):
    mode: Literal["auto", "manual"]
    value_us: Annotated[float, Field(gt=0)] | None = None

    @model_validator(mode="after")
    def _manual_needs_value(self) -> Self:
        if self.mode == "manual" and self.value_us is None:
            raise ValueError("manual exposure needs value_us")
        if self.mode == "auto" and self.value_us is not None:
            raise ValueError("auto exposure takes no value_us")
        return self


class WhiteBalance(_Strict):
    mode: Literal["auto", "manual"]
    kelvin: Annotated[int, Field(gt=0)] | None = None

    @model_validator(mode="after")
    def _manual_needs_kelvin(self) -> Self:
        if self.mode == "manual" and self.kelvin is None:
            raise ValueError("manual white balance needs kelvin")
        if self.mode == "auto" and self.kelvin is not None:
            raise ValueError("auto white balance takes no kelvin")
        return self


class Zoom(_Strict):
    value: float


class CameraProfile(_Strict):
    """Settings applied to the camera on every open, then read back.

    The C920 needs auto modes off before manual values are accepted; that is a
    driver concern (TD-04), not part of this model.
    """

    resolution: tuple[Annotated[int, Field(gt=0)], Annotated[int, Field(gt=0)]]
    pixel_format: Literal["mjpeg", "yuyv"] | None = None  # UVC only
    exposure: Exposure
    gain: ManualOrAuto
    white_balance: WhiteBalance
    focus: ManualOrAuto
    zoom: Zoom | None = None  # motorized lens only
    power_line_hz: Literal[50, 60] = 60
    low_light_compensation: bool = False
