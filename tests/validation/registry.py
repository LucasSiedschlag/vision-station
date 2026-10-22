"""The types the bench covers, their cases, and the table of tracked exceptions (NFR-MAI-5, VIA-0074).

A type registered by the program with no case fails the suite; a check that fails must be in `EXCEPTIONS`
with the task that will fix it, and a listed check that passes fails the suite too (strict xfail).
"""

import importlib
import re

import pytest

from validation.case import Case
from vision_station.locators import get_locator, locator_types
from vision_station.tools import get_tool, tool_types

CHECKS = tuple(f"V{n}" for n in range(1, 11))
LOCATOR_CHECKS = {"V1", "V2", "V3", "V4", "V8", "V9"}  # a locator has no score, criteria or reason codes
LOCATOR_ONLY = {"V4.rotation"}  # a tool is cut upright by the pipeline, so only a locator can fail to follow a turn
TOOL_ONLY = {"V7", "V10"}  # what a tool draws, and the tools reference
TASK = re.compile(r"VIA-\d{4}")

# (kind, type, version, check) -> the task that fixes it. Only what was seen failing goes here.
EXCEPTIONS: dict[tuple[str, str, int, str], str] = {
    ("locator", "blob", 1, "V4.rotation"): "VIA-0123",  # no pose: the v2 gives it
    ("locator", "template", 1, "V4.rotation"): "VIA-0123",
    **{("tool", name, 1, "V10"): "VIA-0075" for name in ("code", "color", "detect", "pattern")},  # the tools reference (D13)
    ("tool", "detect", 1, "V8"): "VIA-0112",  # the latency is the model's, stated in its card (FR-MDL-6)
}


def _program(run) -> bool:
    return run.__module__.startswith("vision_station.")  # a test may register fakes


TYPES: list[tuple[str, str, int]] = (
    [("tool", n, v) for n, v in tool_types() if _program(get_tool(n, v).run)]
    + [("locator", n, v) for n, v in locator_types() if _program(get_locator(n, v).locate)]
)


def case_for(kind: str, name: str, version: int) -> Case | None:
    try:
        module = importlib.import_module(f"validation.cases.{name}")
    except ModuleNotFoundError as exc:
        if exc.name != f"validation.cases.{name}":
            raise
        return None
    return getattr(module, "TOOLS" if kind == "tool" else "LOCATORS", {}).get(version)


def applies(kind: str, check: str) -> bool:
    if check in LOCATOR_ONLY:
        return kind == "locator"
    if check in TOOL_ONLY:
        return kind == "tool"
    return kind == "tool" or check.split(".")[0] in LOCATOR_CHECKS


def entries(check: str, table: dict | None = None):
    """The types a check runs on, as pytest params; a listed exception is a strict xfail."""
    table = EXCEPTIONS if table is None else table
    out = []
    for kind, name, version in TYPES:
        if not applies(kind, check):
            continue
        marks = []
        if task := table.get((kind, name, version, check)):
            marks.append(pytest.mark.xfail(strict=True, reason=task))
        out.append(pytest.param(kind, name, version, id=f"{kind}-{name}-v{version}", marks=marks))
    return out
