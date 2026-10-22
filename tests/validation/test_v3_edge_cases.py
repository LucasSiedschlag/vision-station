"""V3: empty, 1x1, flat, saturated and noisy pictures give a result or a refusal, never an exception or a NaN."""

import math
from collections.abc import Mapping

import numpy as np
import pytest

from validation.edge import edge_inputs
from validation.registry import case_for, entries
from vision_station.geometry.pose import Fixture
from vision_station.locators import LocatorError, run_locator
from vision_station.tools import ToolError, run_tool
from vision_station.tools.base import ToolResult

INPUTS = edge_inputs()


def _numbers(value, where):
    """Every number inside a result is finite."""
    if isinstance(value, Mapping):
        for k, v in value.items():
            _numbers(v, f"{where}.{k}")
    elif isinstance(value, (list, tuple)):
        for i, v in enumerate(value):
            _numbers(v, f"{where}[{i}]")
    elif isinstance(value, (float, np.floating, int, np.integer)) and not isinstance(value, bool):
        assert math.isfinite(value), f"{where} is {value}"


@pytest.mark.parametrize("picture", INPUTS)
@pytest.mark.parametrize("kind,name,version", entries("V3"))
def test_a_strange_picture_gives_a_result_or_a_refusal(kind, name, version, picture):
    case = case_for(kind, name, version)
    image = INPUTS[picture]
    if kind == "tool":
        try:
            result = run_tool(name, version, image, case.params, case.files)
        except ToolError:
            return
        assert isinstance(result, ToolResult) and isinstance(result.passed, bool)
        assert math.isfinite(result.score) and 0.0 <= result.score <= 1.0
        _numbers(result.values, "values")
        _numbers(result.details, "details")
        for c in result.criteria:
            _numbers([c.score, c.value, c.limit], c.code)
    else:
        try:
            fixture = run_locator(name, version, image, case.params, case.files)
        except LocatorError:
            return
        assert fixture is None or isinstance(fixture, Fixture)
        if fixture is not None:
            _numbers([*fixture.rect, fixture.angle, fixture.scale, fixture.score], "fixture")
            assert 0.0 <= fixture.score <= 1.0 and fixture.rect[0] <= fixture.rect[2] and fixture.rect[1] <= fixture.rect[3]
