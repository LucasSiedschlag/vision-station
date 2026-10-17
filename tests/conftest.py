"""Checks every tool result of every test against the result contract (TD-22, FR-INS-14)."""

import dataclasses

import pytest

from vision_station.core.errors import REASON_CODES
from vision_station.tools import base


def _checked(tool: base.ToolType):
    def run(region, params, files):
        result = tool.run(region, params, files)
        if isinstance(result, base.ToolResult) and result.criteria:
            assert result.passed == all(c.passed for c in result.criteria), f"{tool.name}: verdict and criteria disagree"
            assert result.score == min(c.score for c in result.criteria), f"{tool.name}: score is not its lowest criterion"
            for c in result.criteria:
                assert f"{tool.name}.{c.code}" in REASON_CODES, f"{tool.name}.{c.code} is not in REASON_CODES"
                assert c.measure is None or c.measure in result.units, f"{tool.name}.{c.code}: measure without a unit"
        return result

    return run


@pytest.fixture(autouse=True)
def _tool_results_follow_the_contract(monkeypatch):
    # only the tools of the program: a test that registers its own fake tool checks what it wants
    for key, tool in list(base._REGISTRY.items()):
        if tool.run.__module__.startswith("vision_station.tools."):
            monkeypatch.setitem(base._REGISTRY, key, dataclasses.replace(tool, run=_checked(tool)))
