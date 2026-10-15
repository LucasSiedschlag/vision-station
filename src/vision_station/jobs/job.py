"""The job definition (`job.yaml`, architecture §4.2)."""

from datetime import datetime
from typing import Annotated, Any, Literal, Self
from uuid import UUID

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

# ROI names every job can use without declaring them: the whole frame, and the
# anchor (what the locator found: a box, a part, a label...)
BUILTIN_ROIS = frozenset({"anchor", "frame"})

Fraction = Annotated[float, Field(ge=0, le=1)]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _check_rect(rect: tuple[float, float, float, float]) -> None:
    x0, y0, x1, y1 = rect
    if not (x0 < x1 and y0 < y1):
        raise ValueError("rect must be [x0, y0, x1, y1] with x0 < x1 and y0 < y1")


class Ui(_Strict):
    """Texts the operator screen shows for this job (None = the language file default)."""

    waiting: str | None = None


class JobInfo(_Strict):
    id: UUID  # stays the same across versions
    name: Annotated[str, Field(min_length=1)]
    version: Annotated[int, Field(ge=1)]
    parent_version: Annotated[int, Field(ge=1)] | None = None
    author: str
    created_at: datetime
    description: str = ""
    notes: str = ""  # what changed in this version (asked on save)

    @model_validator(mode="after")
    def _parent_is_older(self) -> Self:
        if self.parent_version is not None and self.parent_version >= self.version:
            raise ValueError("parent_version must be lower than version")
        return self


class Trigger(_Strict):
    """When an inspection starts (TD-19).

    image_presence: an object is present and still in `presence_roi`.
    manual / external: started by the operator or by another system.
    continuous: no trigger, every frame is inspected (for example reading codes).
    """

    mode: Literal["image_presence", "manual", "external", "continuous"] = "image_presence"
    presence_roi: tuple[Fraction, Fraction, Fraction, Fraction] | None = None  # fractions of the frame
    still_ms: Annotated[int, Field(gt=0)] | None = None
    rearm: Literal["object_absent"] = "object_absent"
    # how the image is compared with the empty scene (presence) and with the previous frame (motion)
    diff_threshold: Annotated[int, Field(ge=1, le=255)] = 25  # gray levels that count as a change
    min_area: Annotated[float, Field(gt=0, le=1)] = 0.05  # fraction of the region that must differ to count as present
    motion_area: Annotated[float, Field(gt=0, le=1)] = 0.01  # fraction that must change between frames to count as moving

    @model_validator(mode="after")
    def _presence_settings(self) -> Self:
        if self.mode == "image_presence":
            if self.presence_roi is None or self.still_ms is None:
                raise ValueError("image_presence needs presence_roi and still_ms")
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
    similarity_min: Annotated[float, Field(ge=0, le=1)] = 0.6  # live view vs. reference image (verification)
    anchor_tolerance: Annotated[float, Field(gt=0, le=1)] = 0.05  # allowed anchor shift, as a fraction of the frame


class Locator(_Strict):
    type: str
    version: Annotated[int, Field(ge=1)]
    params: dict[str, Any] = {}


class Roi(_Strict):
    relative_to: Literal["anchor", "frame"]
    rect: tuple[Fraction, Fraction, Fraction, Fraction]

    @model_validator(mode="after")
    def _valid_rect(self) -> Self:
        _check_rect(self.rect)
        return self


class Geometry(_Strict):
    locator: Locator | None = None  # without one, ROIs can only be relative to the frame
    rois: dict[str, Roi] = {}

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        clash = BUILTIN_ROIS & self.rois.keys()
        if clash:
            raise ValueError(f"ROI names reserved: {sorted(clash)}")
        if self.locator is None:
            anchored = sorted(n for n, r in self.rois.items() if r.relative_to == "anchor")
            if anchored:
                raise ValueError(f"ROIs {anchored} are relative to the anchor but the job has no locator")
        return self


class Tool(_Strict):
    """One inspection step: a type (color, code, pattern, detect...) looking at one region."""

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
    tools: Annotated[list[Tool], Field(min_length=1)]
    decision: Literal["all_pass"] = "all_pass"
    ui: Ui = Ui()

    @model_validator(mode="after")
    def _tools_are_consistent(self) -> Self:
        ids = [t.id for t in self.tools]
        if len(ids) != len(set(ids)):
            raise ValueError("tool ids must be unique")
        known = BUILTIN_ROIS | self.geometry.rois.keys()
        for tool in self.tools:
            if tool.roi not in known:
                raise ValueError(f"tool '{tool.id}' uses unknown ROI '{tool.roi}'")
            if tool.roi == "anchor" and self.geometry.locator is None:
                raise ValueError(f"tool '{tool.id}' uses the anchor but the job has no locator")
        return self


def parse_job(text: str) -> Job:
    """Parse and validate the text of a `job.yaml`."""
    return Job.model_validate(yaml.safe_load(text))


def dump_job(job: Job) -> str:
    """Write a job as YAML, in the field order of the model."""
    return yaml.safe_dump(job.model_dump(mode="json"), sort_keys=False, allow_unicode=True)
