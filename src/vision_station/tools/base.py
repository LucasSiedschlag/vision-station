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

from vision_station.jobfiles import JobFiles


class ToolError(Exception):
    """A job refers to a tool the software cannot run, or gives it invalid parameters."""


@dataclass(frozen=True)
class ToolResult:
    passed: bool
    score: float  # 0..1, how far from failing (1 = fully satisfied)
    values: Mapping[str, Any] = field(default_factory=dict)  # fields a job's `reason_fail` text can use
    details: Mapping[str, Any] = field(default_factory=dict)  # for the screen and the log

    def reason(self, template: str) -> str:
        """The job's `reason_fail` text with this result's values filled in."""
        try:
            return template.format_map(self.values)
        except (KeyError, IndexError, ValueError):
            return template  # a typo in the text must not hide the failure


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
