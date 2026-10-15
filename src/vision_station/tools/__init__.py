"""Inspection tools. Importing the package registers the built-in ones."""

from collections.abc import Mapping

from vision_station.jobfiles import JobFileError, check_files
from vision_station.jobs import Job
from vision_station.tools import code as _code  # noqa: F401  (registers the tool)
from vision_station.tools import color as _color  # noqa: F401
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


def check_job_tools(job: Job, files: Mapping[str, bytes] | None = None) -> None:
    """Refuse a job that uses a tool or version this software cannot run, bad parameters, or (when the
    job's files are given) a file a tool needs that is not there."""
    for tool in job.tools:
        try:
            params = validate_params(tool.type, tool.version, tool.params)
            if files is not None:
                check_files(f"tool '{tool.id}'", get_tool(tool.type, tool.version).needs(params), files)
        except (ToolError, JobFileError) as exc:
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
