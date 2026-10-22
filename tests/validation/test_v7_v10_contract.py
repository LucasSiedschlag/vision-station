"""V7 a tool draws what it measured, V10 the tools reference has a section for it (architecture §15.3).
Neither exists yet: the types are listed in `registry.EXCEPTIONS` until the tasks that build them are done."""

import re
from pathlib import Path

import pytest

from validation.registry import entries
from vision_station.tools import get_tool

REFERENCE = Path(__file__).resolve().parents[2] / "docs" / "tools-reference.md"  # D13: one `## `name`` section per tool


@pytest.mark.parametrize("kind,name,version", entries("V7"))
def test_the_tool_draws_what_it_measured(kind, name, version):
    assert callable(getattr(get_tool(name, version), "overlay", None)), f"{name} v{version} has no overlay (frame coordinates)"


@pytest.mark.parametrize("kind,name,version", entries("V10"))
def test_the_tools_reference_has_a_section_for_the_tool(kind, name, version):
    assert REFERENCE.exists(), "docs/tools-reference.md does not exist"
    assert re.search(rf"^## `{name}`", REFERENCE.read_text(encoding="utf-8"), re.M), f"no section for `{name}`"
