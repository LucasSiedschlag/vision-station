"""Inspection tools. Importing the package registers the built-in ones."""

from collections.abc import Mapping

from vision_station.core.calibration import CALIBRATION_FILE
from vision_station.core.jobfiles import JobFileError, check_files
from vision_station.jobs import Job
from vision_station.tools import blob as _blob  # noqa: F401  (registers the tool)
from vision_station.tools import brightness as _brightness  # noqa: F401
from vision_station.tools import code as _code  # noqa: F401  (registers the tool)
from vision_station.tools import color as _color  # noqa: F401
from vision_station.tools import detect as _detect  # noqa: F401
from vision_station.tools import pattern as _pattern  # noqa: F401
from vision_station.tools.base import (
    CriterionSpec,
    ToolError,
    ToolResult,
    ToolType,
    get_tool,
    register,
    run_tool,
    tool_types,
    uses_millimetres,
    validate_params,
)


def check_job_tools(job: Job, files: Mapping[str, bytes] | None = None) -> None:
    """Refuse a job that uses a tool or version this software cannot run, bad parameters, or (when the
    job's files are given) a file a tool needs that is not there."""
    for tool in job.tools:
        try:
            params = validate_params(tool.type, tool.version, tool.params)
            if files is not None:
                type_ = get_tool(tool.type, tool.version)
                check_files(f"tool '{tool.id}'", type_.needs(params), files)
                if uses_millimetres(type_, params) and CALIBRATION_FILE not in files:
                    raise ToolError(f"a size in millimetres needs a calibration of the job ({CALIBRATION_FILE}, FR-INS-15)")
        except (ToolError, JobFileError) as exc:
            raise ToolError(f"tool '{tool.id}': {exc}") from exc


__all__ = [
    "CriterionSpec",
    "ToolError",
    "ToolResult",
    "ToolType",
    "check_job_tools",
    "get_tool",
    "register",
    "run_tool",
    "tool_types",
    "uses_millimetres",
    "validate_params",
]
