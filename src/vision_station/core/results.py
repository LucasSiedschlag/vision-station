"""The outcome of one inspection, as the station controller and the screen see it (architecture §10.3, TD-22)."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Literal


class Outcome(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    ERROR = "ERROR"  # the system could not inspect; never shown as PASS (FR-INS-6)


# what a measured value is: a fraction 0..1 (shown as %), a count, or a score of the tool's own scale
Unit = Literal["fraction", "count", "score"]


@dataclass(frozen=True)
class Criterion:
    """One check of a tool. `code` is stable: `<tool type>.<code>` is the reason code of a failure (FR-INS-14)."""

    code: str
    kind: Literal["min", "max", "rule"]  # a lower limit, an upper limit, or a yes/no rule (a class, a missing class)
    passed: bool
    score: float  # this check's part of the tool's score: 1.0 when satisfied
    measure: str | None = None  # the value it checks, a key of the tool's measures; None for a rule
    value: float | None = None
    limit: float | None = None

    @property
    def margin(self) -> float | None:
        """How far the value is inside the limit, in the value's unit (negative: outside); None for a rule."""
        if self.value is None or self.limit is None or self.kind == "rule":
            return None
        return self.value - self.limit if self.kind == "min" else self.limit - self.value


@dataclass(frozen=True)
class ToolReport:
    """One tool's part of a result: what it measured and why it passed or failed."""

    id: str
    type: str
    version: int
    passed: bool
    score: float
    values: Mapping[str, float] = field(default_factory=dict)  # the numeric measures, by name
    units: Mapping[str, Unit] = field(default_factory=dict)
    criteria: tuple[Criterion, ...] = ()
    affects_result: bool = True  # an informative tool is run and recorded but never decides (FR-INS-13)
    error: str = ""  # an informative tool that could not run: why (a deciding one makes the result ERROR instead)

    @property
    def decisive(self) -> Criterion | None:
        """The criterion that set the score: the lowest, the first one on a tie."""
        return min(self.criteria, key=lambda c: c.score, default=None)

    @property
    def margin(self) -> float | None:
        decisive = self.decisive
        return decisive.margin if decisive else None


@dataclass(frozen=True)
class ReasonCode:
    tool: str
    code: str  # `<tool type>.<criterion>`, e.g. `color.min_fraction`


TriggerSource = Literal["image", "manual", "api", "machine"]


@dataclass(frozen=True)
class TriggerInfo:
    """What started an inspection."""

    source: TriggerSource  # image: the presence detector or the continuous mode; manual: the screen; api: another program
    reference: str = ""  # what the caller gave with the trigger (FR-INT-1)
    part_id: str = ""  # the machine's id of the part (R3)
    at: float | None = None  # wall-clock time of the trigger, epoch seconds


@dataclass(frozen=True)
class ResultJob:
    """Exactly which job version decided."""

    id: str
    name: str
    version: int
    number: int | None = None  # the machine's job number (R3)
    content_hash: str | None = None  # of the saved version's files (store.archive.content_hash); None for a draft


@dataclass(frozen=True)
class FixturePose:
    """Where a locator found the part. Angle and scale are None until the locators measure them (R1)."""

    name: str
    x: float  # centre, as a fraction of the frame width
    y: float  # centre, as a fraction of the frame height
    angle: float | None
    scale: float | None
    score: float


@dataclass(frozen=True)
class InspectionResult:
    outcome: Outcome
    reason: str = ""  # Portuguese, for the operator (FR-INS-7)
    scores: Mapping[str, float] = field(default_factory=dict)
    details: Mapping[str, Any] = field(default_factory=dict)
    duration_s: float = 0.0
    error_code: int = 0  # ERROR only: a code of the catalog (core/errors.py, FR-INS-14); 0 otherwise
    reason_codes: tuple[ReasonCode, ...] = ()  # FAIL: which deciding tools failed and why
    tools: tuple[ToolReport, ...] = ()
    fixtures: tuple[FixturePose, ...] = ()
    # set by the station controller, not by the pipeline
    sequence: int | None = None  # +1 per inspection, wraps at 2**32: how a PLC sees a missed result
    job: ResultJob | None = None
    trigger: TriggerInfo | None = None
    acquired_at: float | None = None  # wall-clock times, epoch seconds
    decided_at: float | None = None
    simulated: bool = False  # from a simulated camera, the editor or a replay: never signalled to a machine (FR-INT-12)
