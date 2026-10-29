"""The job definition (`job.yaml`, architecture §4.2, format 3)."""

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


class PresenceTrigger(_Strict):
    """`image_presence`: an object is present and still in `roi` (TD-19). Every parameter is written (FR-JOB-16)."""

    roi: tuple[Fraction, Fraction, Fraction, Fraction]  # fractions of the frame
    still_ms: Annotated[int, Field(gt=0)]  # stillness before the picture
    rearm: Literal["object_absent"]
    # how the image is compared with the empty scene (presence) and with the previous frame (motion)
    diff_threshold: Annotated[int, Field(ge=1, le=255)]  # gray levels that count as a change
    min_area: Annotated[float, Field(gt=0, le=1)]  # fraction of the region that must differ to count as present
    motion_area: Annotated[float, Field(gt=0, le=1)]  # fraction that must change between frames to count as moving

    @model_validator(mode="after")
    def _roi_has_area(self) -> Self:
        _check_rect(self.roi)
        return self


class ExternalTrigger(_Strict):
    """`external`: started from outside (the machine, the local API). Which line, edge or protocol carries it is the
    station's, never the job's (architecture §4.6)."""

    delay_ms: Annotated[int, Field(ge=0, le=1000)]  # wait this long after the signal before the picture (FR-TRG-6)
    debounce_ms: Annotated[int, Field(ge=0, le=65)]  # the input filter against bounce (FR-TRG-8), applied where the line is read


class ContinuousTrigger(_Strict):
    """`continuous`: every frame is inspected, not more often than `interval_ms` (FR-TRG-7, TD-31)."""

    interval_ms: Annotated[int, Field(ge=0, le=10_000)]  # 0: as fast as the PC allows


class TriggerBlock(_Strict):
    """When an inspection starts. The type decides which sub-block is read; one of another type may be present and is
    ignored, so switching the type in the editor keeps what the person typed (docs/job-format.md §7)."""

    type: Literal["image_presence", "external", "manual", "continuous"]
    image_presence: PresenceTrigger | None = None
    external: ExternalTrigger | None = None
    continuous: ContinuousTrigger | None = None

    @model_validator(mode="after")
    def _written_in_full(self) -> Self:
        if self.type != "manual" and getattr(self, self.type) is None:
            raise ValueError(f"trigger type '{self.type}' needs its block '{self.type}' with every parameter written")
        return self


class ImageBlock(_Strict):
    profile: str  # relative path inside the .vjob, e.g. camera/profile.yaml
    calibration: str | None = None  # relative path of the calibration (FR-INS-15); None: the job is not calibrated


class Acquisition(_Strict):
    """How and when the picture is taken, in one block (TD-32, FR-JOB-16): the trigger and the image."""

    trigger: TriggerBlock
    image: ImageBlock


def acquisition_block(type: str = "manual", profile: str = "camera/profile.yaml", **blocks: dict[str, Any]) -> dict[str, Any]:
    """A block with every parameter written, as the editor writes it, for scripts and tests: the defaults of the editor,
    with the parameters of `blocks` (by sub-block name) changed. The software has no defaults of its own: a saved block
    always says what it means (FR-JOB-16)."""
    full: dict[str, Any] = {
        "image_presence": {"roi": [0.1, 0.1, 0.9, 0.9], "still_ms": 500, "rearm": "object_absent", "diff_threshold": 25, "min_area": 0.05, "motion_area": 0.01},
        "external": {"delay_ms": 0, "debounce_ms": 0},
        "continuous": {"interval_ms": 500},
    }
    trigger: dict[str, Any] = {"type": type}
    for name, defaults in full.items():
        if name == type or name in blocks:
            trigger[name] = {**defaults, **blocks.get(name, {})}
    return {"trigger": trigger, "image": {"profile": profile, "calibration": None}}


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
    # The name of a group in `Job.groups`: of the members of a group one passing tool is enough (TD-33, FR-INS-17).
    # Written only when set, like `affects_result`, so a job that does not use it is the same file as before.
    group: Annotated[str, Field(min_length=1)] | None = Field(default=None, exclude_if=lambda v: v is None)


class Group(_Strict):
    """A set of tools that pass together when any of them passes (an OR; TD-33). A failed group says this text instead of
    the texts of its members; it has no `{fields}`, since its members measure different things."""

    reason_fail: Text


class Job(_Strict):
    format: Literal[3]
    job: JobInfo
    acquisition: Acquisition
    quality: Quality
    geometry: Geometry
    tools: Annotated[list[Tool], Field(min_length=1)]
    groups: dict[Annotated[str, Field(min_length=1)], Group] = Field(default={}, exclude_if=lambda v: not v)
    decision: Literal["all_pass"] = "all_pass"  # over the tools with no group and over the groups (TD-33)
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
        self._check_groups()
        return self

    def _check_groups(self) -> None:
        """TD-33: every group is declared and has two members that decide the result. An OR over a tool that does not
        decide, or over one tool, would be a trap: the editor shows a group that does nothing."""
        members: dict[str, list[Tool]] = {name: [] for name in self.groups}
        for tool in self.tools:
            if tool.group is None:
                continue
            if tool.group not in members:
                raise ValueError(f"tool '{tool.id}' is in group '{tool.group}', which is not declared in groups")
            if not tool.affects_result:
                raise ValueError(f"tool '{tool.id}' is in group '{tool.group}' but does not decide the result")
            members[tool.group].append(tool)
        for name, tools in members.items():
            if len(tools) < 2:
                raise ValueError(f"group '{name}' needs at least two tools: it has {len(tools)}")


def parse_job(text: str) -> Job:
    """Parse and validate the text of a `job.yaml`. A job of an older format is refused: nothing needs reading one (TD-21)."""
    data = yaml.safe_load(text)
    if isinstance(data, dict) and isinstance(data.get("format"), int) and data["format"] < 3:
        raise ValueError(f"job format {data['format']} is no longer supported: make the job again (format 3)")
    return Job.model_validate(data)


def dump_job(job: Job) -> str:
    """Write a job as YAML, in the field order of the model."""
    data = job.model_dump(mode="json")
    if not data["job"]["tuned"]:
        del data["job"]["tuned"]
    return yaml.safe_dump(data, sort_keys=False, allow_unicode=True)
