"""Tolerance limits proposed from samples labelled good and bad (FR-UI-14, document 05 §19.3).

For one criterion of a tool, the values its measure took on the *Boa* and the *Ruim* samples say where the limit
could be. With both kinds the limit goes in the middle of the gap between the worst good value and the nearest bad
one, and the margin on each side is told. With good samples only, it goes a margin away from the worst good one.
When a bad sample is measured as well as a good one, nothing separates them and nothing is proposed: it is said
so, never forced. A proposal is only a proposal; the person applies or discards it, and the fine-tune screen of the
supervisor uses the same function (VIA-0067).

Pure functions, so they are tested without a camera or a job.
"""

import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

Side = Literal["min", "max"]  # the limit the value must stay above (min) or below (max)

MIN_GOOD = 3  # good samples needed to propose a limit (document 05 §19.1); bad ones are never required
MARGIN = 0.20  # of the worst good value, when there are no bad samples to put the limit between (document 02 §7)


@dataclass(frozen=True)
class Sample:
    """What one labelled picture gave for one measure of one tool."""

    good: bool  # a *Boa* sample (expected PASS); False: a *Ruim* one (expected FAIL)
    value: float


@dataclass(frozen=True)
class Proposal:
    side: Side
    proposed: float | None  # None: nothing is proposed, and `reason` says why
    reason: str  # "", "few_good", "overlap" or "bounds"
    worst_good: float | None  # the good value nearest the limit
    nearest_bad: float | None  # the bad value nearest the limit on this side
    margin_good: float | None  # from the proposed limit to the worst good value
    margin_bad: float | None  # from the proposed limit to the nearest bad value
    basis: Literal["gap", "from_good", ""]


def _round(value: float, unit: str, side: Side, fits: Callable[[float], bool]) -> float:
    """A value a person types: whole for a count, two decimals for a share or a score, finer if the gap is narrow.
    `fits` says whether a rounded value still separates the samples."""
    if unit == "count":
        return float(math.ceil(value) if side == "min" else math.floor(value))
    for places in (2, 3, 4, 6):
        rounded = round(value, places)
        if fits(rounded):
            return rounded
    return value


def propose_limit(
    side: Side,
    good: list[float],
    bad: list[float],
    unit: str,
    bounds: tuple[float | None, float | None] = (None, None),
    margin: float = MARGIN,
    scale: float = 1.0,
) -> Proposal:
    """The limit for one side of a criterion. `bad` holds only the bad values that this side has to keep apart (for a
    criterion with two limits, the ones on its own side of the good values). `scale` is the size of the measure's
    range, so a margin is not nothing when the worst good value is zero."""
    if len(good) < MIN_GOOD:
        return Proposal(side, None, "few_good", None, None, None, None, "")
    worst = min(good) if side == "min" else max(good)
    # a bad value on the wrong side of the worst good one cannot be told apart from the good ones
    if any((b >= worst) if side == "min" else (b <= worst) for b in bad):
        return Proposal(side, None, "overlap", worst, min(bad, key=lambda b: abs(b - worst)), None, None, "")
    if bad:
        nearest = max(bad) if side == "min" else min(bad)
        raw, basis = (worst + nearest) / 2, "gap"
    else:
        nearest = None
        step = 0.0 if unit == "count" else margin * max(abs(worst), 0.05 * scale)
        raw, basis = (worst - step if side == "min" else worst + step), "from_good"

    def separates(v: float) -> bool:
        """Every good value passes, and every bad one fails: the limit lies between them, open at the bad end."""
        if side == "min":
            return v <= worst and (nearest is None or v > nearest)
        return v >= worst and (nearest is None or v < nearest)

    value = _round(raw, unit, side, separates)
    lo, hi = bounds
    if lo is not None:
        value = max(value, lo)
    if hi is not None:
        value = min(value, hi)
    if not separates(value):
        return Proposal(side, None, "bounds", worst, nearest, None, None, "")
    return Proposal(side, value, "", worst, nearest, abs(worst - value), None if nearest is None else abs(value - nearest), basis)  # type: ignore[arg-type]


def _bounds(entry: Any, param: str) -> tuple[float | None, float | None]:
    """The least and the most the parameter may be, from its schema (an exclusive bound is taken as just inside)."""
    prop = entry.params.model_json_schema().get("properties", {}).get(param, {})
    for option in [prop, *prop.get("anyOf", [])]:
        if option.get("type") in ("number", "integer"):
            lo = option.get("minimum", option.get("exclusiveMinimum"))
            hi = option.get("maximum", option.get("exclusiveMaximum"))
            if "exclusiveMinimum" in option and lo is not None:
                lo = lo + (1 if option["type"] == "integer" else 1e-6)
            if "exclusiveMaximum" in option and hi is not None:
                hi = hi - (1 if option["type"] == "integer" else 1e-6)
            return lo, hi
    return None, None


def propose_for_criterion(tool: Any, entry: Any, spec: Any, rows: list[tuple[Any, ...]], margin: float = MARGIN) -> list[dict[str, Any]]:
    """The proposals for one criterion of one tool of a job, from the rows of the batch test (image, kind, expected,
    ok, result, message). A bad sample that another deciding tool fails and this one passes is left out for this
    tool: that defect is somebody else's to catch, and counting it would call a good gauge "overlapping". For a member
    of a group (an OR, TD-33) a good picture it did not match is left out too: another member passed it, and counting its
    value would drag the limit to a member that always matches, so the group would pass on any picture."""
    good: list[float] = []
    bad: list[float] = []
    for _image, kind, _expected, _ok, result, _message in rows:
        if kind not in ("good", "bad") or result is None:
            continue
        report = next((t for t in result.tools if t.id == tool.id), None)
        value = None if report is None else report.values.get(spec.value)
        if value is None:
            continue
        if kind == "good":
            if tool.group is not None and not report.passed:
                continue  # another member of the group carried this picture: it says nothing about this member's limit (TD-33)
            good.append(float(value))
        elif not (report.passed and any(not t.passed for t in result.tools if t.id != tool.id and t.affects_result)):
            bad.append(float(value))
    params = entry.params.model_validate(dict(tool.params))
    low, high = spec.range
    scale = (high - low) if high is not None else (max(good) if good else 1.0)
    out: list[dict[str, Any]] = []
    for side, param in (("min", spec.min_param), ("max", spec.max_param)):
        if param is None:
            continue
        if spec.min_param and spec.max_param and good:  # two limits: each keeps apart the bad values on its own side
            mine = [b for b in bad if (b <= max(good) if side == "min" else b >= min(good))]
        else:
            mine = bad
        found = propose_limit(side, good, mine, spec.unit, _bounds(entry, param), margin, scale or 1.0)  # type: ignore[arg-type]
        current = getattr(params, param, None)  # the value in force: a parameter left out of the job has its default
        out.append(dict(
            tool=tool.id, criterion=spec.value, label=spec.label, param=param, side=side, unit=spec.unit,
            current=None if current is None else float(current), proposed=found.proposed, reason=found.reason, basis=found.basis,
            worst_good=found.worst_good, nearest_bad=found.nearest_bad, margin_good=found.margin_good, margin_bad=found.margin_bad,
            good_n=len(good), bad_n=len(mine),
        ))
    return out
