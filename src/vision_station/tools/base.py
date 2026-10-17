"""The tool contract and the registry (TD-19, architecture §3).

A tool looks at one region of a frame and answers pass/fail with a score. The
pipeline crops the region from the job's ROI and calls the tool, so a tool never
sees the whole frame, the camera or the job; only the job's files it names in its
parameters (a template, a model), through `JobFiles`. A job refers to a tool by type name
and version; a version that is no longer supported refuses the job instead of
running different logic.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from pydantic import BaseModel, ValidationError

from vision_station.algorithms.measures import at_least, at_most
from vision_station.core.jobfiles import JobFiles
from vision_station.core.results import Criterion, Unit


class ToolError(Exception):
    """A job refers to a tool the software cannot run, or gives it invalid parameters."""


@dataclass(frozen=True)
class ToolResult:
    passed: bool
    score: float  # 0..1, how far from failing (1 = fully satisfied)
    values: Mapping[str, Any] = field(default_factory=dict)  # fields a job's `reason_fail` text can use
    details: Mapping[str, Any] = field(default_factory=dict)  # for the screen and the log
    criteria: tuple[Criterion, ...] = ()  # each check, so a failure has a reason code (FR-INS-14)
    units: Mapping[str, Unit] = field(default_factory=dict)  # the keys of `values` that are measures, and their unit

    def reason(self, template: str) -> str:
        """The job's `reason_fail` text with this result's values filled in."""
        try:
            return template.format_map(self.values)
        except (KeyError, IndexError, ValueError):
            return template  # a typo in the text must not hide the failure


def judged(criteria: list[Criterion], **fields: Any) -> ToolResult:
    """A result whose score and verdict come from its criteria: the lowest score, passed only if all pass."""
    if not criteria:
        raise ToolError("the tool has nothing to check with these parameters")
    score = min(c.score for c in criteria)
    return ToolResult(passed=score >= 1.0 and all(c.passed for c in criteria), score=score, criteria=tuple(criteria), **fields)


def minimum(code: str, measure: str, value: float, limit: float) -> Criterion:
    """`value` at least `limit` (algorithms.measures.at_least)."""
    score = at_least(value, limit)
    return Criterion(code, "min", score >= 1.0, score, measure, float(value), float(limit))


def maximum(code: str, measure: str, value: float, limit: float) -> Criterion:
    """A fraction `value` at most `limit` (algorithms.measures.at_most)."""
    score = at_most(value, limit)
    return Criterion(code, "max", score >= 1.0, score, measure, float(value), float(limit))


def count_at_most(code: str, measure: str, value: int, limit: int) -> Criterion:
    """A count at most `limit`: one more is a failure with score 0."""
    score = 1.0 if value <= limit else 0.0
    return Criterion(code, "max", score >= 1.0, score, measure, float(value), float(limit))


def rule(code: str, score: float) -> Criterion:
    """A yes/no check (a class that fails, a class that is missing); `score` 1.0 when satisfied."""
    return Criterion(code, "rule", score >= 1.0, score)


@dataclass(frozen=True)
class ToolType:
    name: str
    version: int
    params: type[BaseModel]
    run: Callable[[np.ndarray, Any, JobFiles], ToolResult]  # (region image, validated params, job files)
    needs: Callable[[Any], list[str]] = lambda params: []  # job files the validated params refer to


_REGISTRY: dict[tuple[str, int], ToolType] = {}


def register(tool: ToolType) -> ToolType:
    key = (tool.name, tool.version)
    if key in _REGISTRY:
        raise ValueError(f"tool {tool.name} v{tool.version} already registered")
    _REGISTRY[key] = tool
    return tool


def tool_types() -> list[tuple[str, int]]:
    return sorted(_REGISTRY)


def get_tool(name: str, version: int) -> ToolType:
    tool = _REGISTRY.get((name, version))
    if tool is None:
        known = [v for (n, v) in _REGISTRY if n == name]
        if known:
            raise ToolError(f"tool '{name}' version {version} is not supported (supported: {sorted(known)})")
        raise ToolError(f"unknown tool '{name}' (available: {sorted({n for n, _ in _REGISTRY})})")
    return tool


def validate_params(name: str, version: int, params: Mapping[str, Any]) -> BaseModel:
    tool = get_tool(name, version)
    try:
        return tool.params.model_validate(dict(params))
    except ValidationError as exc:
        raise ToolError(f"invalid parameters for '{name}' v{version}: {exc}") from exc


def run_tool(name: str, version: int, region: np.ndarray, params: Mapping[str, Any], files: JobFiles | Mapping[str, bytes] | None = None) -> ToolResult:
    tool = get_tool(name, version)
    return tool.run(region, validate_params(name, version, params), files if isinstance(files, JobFiles) else JobFiles(files))
