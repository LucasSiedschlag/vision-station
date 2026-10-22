"""V5 score semantics and V6 reason codes and fields (architecture §15.3), on a passing and a failing region
of every tool. The result contract is also checked on every tool run by `tests/conftest.py`."""

import math
import re
import sys

import pytest

from validation.registry import case_for, entries
from vision_station.core.errors import REASON_CODES
from vision_station.tools import get_tool, run_tool


def _run(name, version, region):
    case = case_for("tool", name, version)
    return run_tool(name, version, region, case.params, case.files)


def _results(name, version):
    case = case_for("tool", name, version)
    return _run(name, version, case.passing), _run(name, version, case.failing)


@pytest.mark.parametrize("kind,name,version", entries("V5"))
def test_the_score_is_below_one_exactly_when_the_tool_fails(kind, name, version):
    good, bad = _results(name, version)
    assert good.passed and not bad.passed, "the case's passing region must pass and its failing region must fail"
    for result in (good, bad):
        assert math.isfinite(result.score) and 0.0 <= result.score <= 1.0
        assert (result.score < 1.0) == (not result.passed)
        for c in result.criteria:
            assert (c.score < 1.0) == (not c.passed), c.code
            if c.margin is not None:
                assert (c.margin >= 0) == c.passed, f"{c.code}: margin {c.margin} and verdict disagree"


def _documented(name, version) -> set[str]:
    doc = sys.modules[get_tool(name, version).params.__module__].__doc__ or ""
    paragraph = doc.split("Fields for `reason_fail`", 1)[1]
    return set(re.findall(r"\{(\w+)\}", paragraph))


@pytest.mark.parametrize("kind,name,version", entries("V6"))
def test_every_criterion_has_a_reason_code_and_every_value_is_documented(kind, name, version):
    documented = _documented(name, version)
    for result in _results(name, version):
        assert result.criteria, "a result with nothing checked has no reason code"
        for c in result.criteria:
            assert f"{name}.{c.code}" in REASON_CODES, f"{name}.{c.code} has no reason code"
            assert c.measure is None or c.measure in result.units
        undocumented = set(result.values) - documented
        assert not undocumented, f"{name}: values a `reason_fail` can use but the module does not document: {sorted(undocumented)}"
