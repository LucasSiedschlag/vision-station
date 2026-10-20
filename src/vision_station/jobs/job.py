"""The job definition (`job.yaml`, architecture §4.2, format 2)."""

from collections.abc import Mapping
from datetime import datetime
from typing import Annotated, Any, Literal, Self
from uuid import UUID

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from vision_station.core.i18n import Bilingual, Language

# The region every job can use without declaring it: the whole frame. A fixture's name is also a region (the whole
# box of what the locator found), and a region can be relative to a fixture (TD-21, architecture §14).
BUILTIN_ROIS = frozenset({"frame"})

Fraction = Annotated[float, Field(ge=0, le=1)]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _check_rect(rect: tuple[float, float, float, float]) -> None:
    x0, y0, x1, y1 = rect
    if not (x0 < x1 and y0 < y1):
        raise ValueError("rect must be [x0, y0, x1, y1] with x0 < x1 and y0 < y1")


class Text(BaseModel):
    """A text written in the job, in both languages (FR-JOB-15, TD-30): `{pt-BR: ..., en: ...}`. An empty one falls back to
    the other, and the editor's *Validar* says so. A bare string is read as Portuguese."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, serialize_by_alias=True)

    pt_br: str = Field(alias="pt-BR", default="")
    en: str = ""

    @model_validator(mode="before")
    @classmethod
    def _bare_text(cls, data: Any) -> Any:
        return {"pt-BR": data} if isinstance(data, str) else data

    def get(self, language: Language | str) -> str:
        """The text in a language, or in the other one when this one is empty."""
        first, second = (self.en, self.pt_br) if language == "en" else (self.pt_br, self.en)
        return first or second

    def missing(self) -> list[Language]:
        """The languages that have no text."""
        return [lang for lang, text in (("pt-BR", self.pt_br), ("en", self.en)) if not text.strip()]  # type: ignore[misc]

    def filled(self, values: Mapping[str, Any] | None = None) -> Bilingual:
        """The text with `values` put into its `{fields}` in each language, as a text that shows in the language asked for.
        A typo in a field name leaves the text as written: it must not hide a failure."""
        def put(text: str) -> str:
            try:
                return text.format_map(values) if values is not None else text
            except (KeyError, IndexError, ValueError):
                return text

        return Bilingual(put(self.get("pt-BR")), put(self.get("en")))


class Ui(_Strict):
    """Texts the operator screen shows for this job (None = the language file default)."""

    waiting: Text | None = None


class JobInfo(_Strict):
    id: UUID  # stays the same across versions
    name: Annotated[str, Field(min_length=1)]
    version: Annotated[int, Field(ge=1)]
    parent_version: Annotated[int, Field(ge=1)] | None = None
    author: str
    created_at: datetime
    description: str = ""
    notes: str = ""  # what changed in this version (asked on save)
    tuned: bool = False  # a fine-tune of tolerances by the supervisor (FR-JOB-14); written only when true

    @model_validator(mode="after")
    def _parent_is_older(self) -> Self:
        if self.parent_version is not None and self.parent_version >= self.version:
            raise ValueError("parent_version must be lower than version")
        return self


DEFAULT_INTERVAL_MS = 500


class Trigger(_Strict):
    """When an inspection starts (TD-19).

    image_presence: an object is present and still in `presence_roi`.
    manual / external: started by the operator or by another system.
    continuous: no trigger, every frame is inspected (for example reading codes), but not more often than
    `interval_ms` (FR-TRG-7, TD-31).
    """

    mode: Literal["image_presence", "manual", "external", "continuous"] = "image_presence"
    presence_roi: tuple[Fraction, Fraction, Fraction, Fraction] | None = None  # fractions of the frame
    still_ms: Annotated[int, Field(gt=0)] | None = None
    rearm: Literal["object_absent"] = "object_absent"
    # continuous: the least time between two inspections; 0 = as fast as the PC allows. 500 ms leaves CPU on tier M
    interval_ms: Annotated[int, Field(ge=0, le=10_000)] = DEFAULT_INTERVAL_MS
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


class FixtureRange(_Strict):
    """How far a found object may be from the one that was taught; outside it the result is ERROR E202, never FAIL (FR-INS-11)."""

    angle: tuple[float, float] = (-15.0, 15.0)  # degrees; NFR-ACC-4 asks for ±10°
    scale: tuple[float, float] = (0.9, 1.1)
    position: tuple[Fraction, Fraction, Fraction, Fraction] | None = None  # the box the centre must stay in, fractions of the frame

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if not (-180.0 <= self.angle[0] <= self.angle[1] <= 180.0):
            raise ValueError("angle must be [min, max] inside -180..180")
        if not (0 < self.scale[0] <= self.scale[1]):
            raise ValueError("scale must be [min, max] with 0 < min <= max")
        if self.position is not None:
            _check_rect(self.position)
        return self


NAME = r"^[A-Za-z][A-Za-z0-9_-]*$"


class FixtureSpec(_Strict):
    """What to find (a locator), where to look for it, and how far from the taught pose it may be."""

    name: Annotated[str, Field(pattern=NAME)]
    locator: Locator
    inside: str | None = None  # the fixture to look in: a part's label, a bottle's cap (FR-INS-12); it comes earlier in the list
    range: FixtureRange = FixtureRange()


class Roi(_Strict):
    relative_to: Annotated[str, Field(min_length=1)]  # `frame`, or the name of a fixture
    rect: tuple[Fraction, Fraction, Fraction, Fraction]

    @model_validator(mode="after")
    def _valid_rect(self) -> Self:
        _check_rect(self.rect)
        return self


class Geometry(_Strict):
    fixtures: list[FixtureSpec] = []  # in the order they are found: a chain is a list, not a graph
    rois: dict[str, Roi] = {}

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        names = [f.name for f in self.fixtures]
        if len(names) != len(set(names)):
            raise ValueError("fixture names must be unique")
        clash = (BUILTIN_ROIS | set(names)) & self.rois.keys()
        if clash or BUILTIN_ROIS & set(names):
            raise ValueError(f"region names reserved or repeated: {sorted(clash | (BUILTIN_ROIS & set(names)))}")
        for i, fixture in enumerate(self.fixtures):
            if fixture.inside is not None and fixture.inside not in names[:i]:
                raise ValueError(f"fixture '{fixture.name}' looks inside '{fixture.inside}', which is not an earlier fixture")
        for name, roi in self.rois.items():
            if roi.relative_to != "frame" and roi.relative_to not in names:
                raise ValueError(f"region '{name}' is relative to '{roi.relative_to}', which is neither the frame nor a fixture")
        return self


class Tool(_Strict):
    """One inspection step: a type (color, code, pattern, detect...) looking at one region."""

    id: Annotated[str, Field(min_length=1)]
    type: str
    version: Annotated[int, Field(ge=1)]
    roi: str
    params: dict[str, Any] = {}
    reason_fail: Text
    # False: informative, run and recorded but never deciding the result (FR-INS-13). Written only when
    # False, so a job that does not use it stays readable by older versions of the program.
    affects_result: bool = Field(default=True, exclude_if=lambda v: v is True)


class Job(_Strict):
    format: Literal[2]
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
        known = BUILTIN_ROIS | self.geometry.rois.keys() | {f.name for f in self.geometry.fixtures}
        for tool in self.tools:
            if tool.roi not in known:
                raise ValueError(f"tool '{tool.id}' uses unknown region '{tool.roi}'")
        if not any(t.affects_result for t in self.tools):
            raise ValueError("at least one tool must decide the result: with only informative tools every part would pass")
        return self


def parse_job(text: str) -> Job:
    """Parse and validate the text of a `job.yaml`. A job of an older format is refused: nothing needs reading one (TD-21)."""
    data = yaml.safe_load(text)
    if isinstance(data, dict) and isinstance(data.get("format"), int) and data["format"] < 2:
        raise ValueError(f"job format {data['format']} is no longer supported: make the job again (format 2)")
    return Job.model_validate(data)


def dump_job(job: Job) -> str:
    """Write a job as YAML, in the field order of the model."""
    data = job.model_dump(mode="json")
    if data["trigger"]["interval_ms"] == DEFAULT_INTERVAL_MS:
        # written only when changed, so a job that does not use it still opens in a version without the field
        del data["trigger"]["interval_ms"]
    if not data["job"]["tuned"]:
        del data["job"]["tuned"]
    return yaml.safe_dump(data, sort_keys=False, allow_unicode=True)
