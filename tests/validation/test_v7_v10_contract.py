"""V7 a tool draws what it measured (VIA-0124), V10 the tools reference has a section for it (architecture §15.3).
V10 does not exist yet: the types are listed in `registry.EXCEPTIONS` until the task that builds it is done."""

import re
from pathlib import Path

import pytest

from validation.registry import case_for, entries
from vision_station.core.results import MAX_MARK_POINTS, MAX_MARKS
from vision_station.pipeline.marks import valid_mark
from vision_station.tools import run_tool

REFERENCE = Path(__file__).resolve().parents[2] / "docs" / "tools-reference.md"  # D13: one `## `name`` section per tool


def _regions(case):
    """Every region of a case that a tool is run on: its passing and failing ones and its golden pictures."""
    yield "passing", case.passing, case.params, case.files
    yield "failing", case.failing, case.params, case.files
    for g in case.goldens:
        yield g.id, g.image, {**case.params, **g.params}, case.files if g.files is None else g.files


@pytest.mark.parametrize("kind,name,version", entries("V7"))
def test_the_marks_are_valid_and_inside_the_region(kind, name, version):
    case = case_for(kind, name, version)
    for label, region, params, files in _regions(case):
        marks = run_tool(name, version, region, params, files).marks
        assert len(marks) <= MAX_MARKS, label
        for mark in marks:
            assert valid_mark(mark, region.shape), f"{label}: {mark}"
            assert len(mark.points) <= MAX_MARK_POINTS, label


@pytest.mark.parametrize("kind,name,version", entries("V7"))
def test_a_failing_region_has_marks_unless_the_case_says_why(kind, name, version):
    case = case_for(kind, name, version)
    marks = run_tool(name, version, case.failing, case.params, case.files).marks
    if case.draws_nothing or case.nothing_on_fail:
        # the reason is a claim: when the tool starts to draw, the claim is to be removed
        assert not marks, f"{name} draws marks now: remove the reason from its case"
    else:
        assert marks, f"{name} v{version} marks nothing on its failing region (Case.nothing_on_fail says why it may)"


@pytest.mark.parametrize("kind,name,version", entries("V7"))
def test_a_tool_that_draws_nothing_draws_nothing_anywhere(kind, name, version):
    case = case_for(kind, name, version)
    if case.draws_nothing:
        assert all(not run_tool(name, version, r, p, f).marks for _, r, p, f in _regions(case)), name


@pytest.mark.parametrize("kind,name,version", entries("V10"))
def test_the_tools_reference_has_a_section_for_the_tool(kind, name, version):
    assert REFERENCE.exists(), "docs/tools-reference.md does not exist"
    assert re.search(rf"^## `{name}`", REFERENCE.read_text(encoding="utf-8"), re.M), f"no section for `{name}`"
