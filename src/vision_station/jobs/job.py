"""The job definition (`job.yaml`, architecture §4.2)."""

from datetime import datetime
from typing import Annotated, Any, Literal, Self
from uuid import UUID

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

# ROI names every job can use without declaring them
BUILTIN_ROIS = frozenset({"box", "frame"})

Fraction = Annotated[float, Field(ge=0, le=1)]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _check_rect(rect: tuple[float, float, float, float]) -> None:
    x0, y0, x1, y1 = rect
    if not (x0 < x1 and y0 < y1):
        raise ValueError("rect must be [x0, y0, x1, y1] with x0 < x1 and y0 < y1")


class JobInfo(_Strict):
    id: UUID  # stays the same across versions
    name: Annotated[str, Field(min_length=1)]
    version: Annotated[int, Field(ge=1)]
    parent_version: Annotated[int, Field(ge=1)] | None = None
    author: str
    created_at: datetime
    description: str = ""

    @model_validator(mode="after")
    def _parent_is_older(self) -> Self:
        if self.parent_version is not None and self.parent_version >= self.version:
            raise ValueError("parent_version must be lower than version")
        return self


class Trigger(_Strict):
    presence_roi: tuple[Fraction, Fraction, Fraction, Fraction]  # fractions of the frame
    still_ms: Annotated[int, Field(gt=0)]
    rearm: Literal["box_absent"] = "box_absent"

    @model_validator(mode="after")
    def _valid_rect(self) -> Self:
        _check_rect(self.presence_roi)
        return self


class Range(_Strict):
    min: float
    max: float

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if self.min > self.max:
            raise ValueError("min must not be greater than max")
        return self


class Quality(_Strict):
    brightness: Range
    sharpness_min_ratio: Annotated[float, Field(gt=0)]  # vs. the reference image


class Locator(_Strict):
    type: str
    version: Annotated[int, Field(ge=1)]
    params: dict[str, Any] = {}


class Roi(_Strict):
    relative_to: Literal["box", "frame"]
    rect: tuple[Fraction, Fraction, Fraction, Fraction]

    @model_validator(mode="after")
    def _valid_rect(self) -> Self:
        _check_rect(self.rect)
        return self


class Geometry(_Strict):
    locator: Locator
    rois: dict[str, Roi] = {}

    @model_validator(mode="after")
    def _no_builtin_names(self) -> Self:
        clash = BUILTIN_ROIS & self.rois.keys()
        if clash:
            raise ValueError(f"ROI names reserved: {sorted(clash)}")
        return self


class Check(_Strict):
    id: Annotated[str, Field(min_length=1)]
    type: str
    version: Annotated[int, Field(ge=1)]
    roi: str
    params: dict[str, Any] = {}
    reason_fail: str


class Job(_Strict):
    format: Literal[1]
    job: JobInfo
    camera_profile: str  # relative path inside the .vjob, e.g. camera/profile.yaml
    trigger: Trigger
    quality: Quality
    geometry: Geometry
    checks: Annotated[list[Check], Field(min_length=1)]
    decision: Literal["all_pass"] = "all_pass"

    @model_validator(mode="after")
    def _checks_are_consistent(self) -> Self:
        ids = [c.id for c in self.checks]
        if len(ids) != len(set(ids)):
            raise ValueError("check ids must be unique")
        known = BUILTIN_ROIS | self.geometry.rois.keys()
        for check in self.checks:
            if check.roi not in known:
                raise ValueError(f"check '{check.id}' uses unknown ROI '{check.roi}'")
        return self


def parse_job(text: str) -> Job:
    """Parse and validate the text of a `job.yaml`."""
    return Job.model_validate(yaml.safe_load(text))


def dump_job(job: Job) -> str:
    """Write a job as YAML, in the field order of the model."""
    return yaml.safe_dump(job.model_dump(mode="json"), sort_keys=False, allow_unicode=True)
