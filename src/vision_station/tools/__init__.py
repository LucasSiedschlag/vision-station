"""Inspection tools. Importing the package registers the built-in ones."""

from vision_station.jobs import Job
from vision_station.tools import code as _code  # noqa: F401  (registers the tool)
from vision_station.tools.base import (
    ToolError,
    ToolResult,
    ToolType,
    get_tool,
    register,
    run_tool,
    tool_types,
    validate_params,
)


def check_job_tools(job: Job) -> None:
    """Refuse a job that uses a tool or version this software cannot run, or bad parameters."""
    for tool in job.tools:
        try:
            validate_params(tool.type, tool.version, tool.params)
        except ToolError as exc:
            raise ToolError(f"tool '{tool.id}': {exc}") from exc


__all__ = [
    "ToolError",
    "ToolResult",
    "ToolType",
    "check_job_tools",
    "get_tool",
    "register",
    "run_tool",
    "tool_types",
    "validate_params",
]
