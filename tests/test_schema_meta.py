"""The parameter schemas say how the screen draws each parameter (VIA-0062, UI-3, frontend.md §9.3, §17):
nothing is left without a level and a group, and the gauges point at real parameters."""

import numpy as np
import pytest

from test_api import env, login  # noqa: F401
from vision_station.core.i18n import render_schema, using
from vision_station.core.schema_labels import GROUPS, LEVELS
from vision_station.locators import get_locator, locator_types
from vision_station.tools import get_tool, run_tool, tool_types

TOOLS = [get_tool(n, v) for n, v in tool_types()]
LOCATORS = [get_locator(n, v) for n, v in locator_types()]
EVERY = [pytest.param(t, id=f"tool-{t.name}") for t in TOOLS] + [pytest.param(t, id=f"locator-{t.name}") for t in LOCATORS]


def objects(schema):
    """The schema of the parameters and of every object it holds (a color range inside a locator)."""
    yield schema
    for definition in schema.get("$defs", {}).values():
        if "properties" in definition:
            yield definition


@pytest.mark.parametrize("entry", EVERY)
def test_every_parameter_has_a_level_and_a_group(entry):
    for schema in objects(entry.params.model_json_schema()):
        for name, prop in schema["properties"].items():
            assert prop.get("x-level") in LEVELS, f"{entry.name}.{name} has no x-level"
            assert prop.get("x-group") in GROUPS, f"{entry.name}.{name} has no x-group"


@pytest.mark.parametrize("entry", EVERY)
def test_only_the_limits_of_a_tool_can_be_fine_tuned(entry):
    for schema in objects(entry.params.model_json_schema()):
        for name, prop in schema["properties"].items():
            if prop.get("x-tunable"):
                assert hasattr(entry, "criteria"), f"{entry.name}.{name}: a locator has nothing to fine-tune"
                assert prop["x-group"] == "criteria" and prop["x-level"] <= 2, f"{entry.name}.{name} is not a limit"


@pytest.mark.parametrize("tool", TOOLS, ids=lambda t: t.name)
def test_every_gauge_points_at_limits_that_exist(tool):
    properties = tool.params.model_json_schema()["properties"]
    for c in tool.criteria:
        assert c.min_param or c.max_param, c.value
        for param in (c.min_param, c.max_param):
            assert param is None or properties[param]["x-group"] == "criteria", f"{tool.name}.{param}"
            assert param is None or properties[param].get("x-tunable"), f"{tool.name}.{param} is a limit the supervisor can tune"
        assert c.level in LEVELS


def test_a_gauge_is_a_measure_the_tool_really_reports():
    frame = np.full((40, 40, 3), (200, 100, 20), np.uint8)
    frame[10:30, 10:30] = (20, 200, 100)  # something to tell apart, so a template is not flat
    reported = {
        "color": run_tool("color", 1, frame, {"hue": [0, 179], "min_fraction": 0.1, "max_fraction": 1.0, "axis": "x", "min_coverage": 0.1, "max_gap": 0.5}),
        "pattern": run_tool("pattern", 1, frame[:, :, 0], {"template": "t.png", "min_count": 0, "max_count": 5, "axis": "x", "min_coverage": 0.1, "max_gap": 0.5}, {"t.png": _png(frame[6:34, 6:34, 0])}),
        "code": run_tool("code", 1, frame, {"min_count": 1, "max_count": 2}),
    }
    for name, result in reported.items():
        measures = {c.measure for c in result.criteria}
        gauges = {c.value for c in get_tool(name, 1).criteria}
        assert measures == gauges, name


def _png(image) -> bytes:
    import cv2

    return cv2.imencode(".png", image)[1].tobytes()


def test_the_codes_stay_the_same_in_english():
    schema = get_tool("color", 1).params.model_json_schema()
    with using("en"):
        english = render_schema(schema)
    for name, prop in schema["properties"].items():
        for key in (k for k in prop if k.startswith("x-") and k != "x-enum-labels"):
            assert english["properties"][name][key] == prop[key], f"{name}.{key}"
    assert english["properties"]["min_fraction"]["title"] != schema["properties"]["min_fraction"]["title"]


def test_the_types_endpoint_gives_the_gauges_in_the_language_asked(env):  # noqa: F811
    client = env.client
    headers = login(env, "maintainer")
    tools = {t["name"]: t for t in client.get("/api/tools", headers=headers).json()["tools"]}
    color = tools["color"]["criteria"]
    assert [c["value"] for c in color] == ["fraction", "coverage", "gap"]
    assert color[0] == {"value": "fraction", "label": "Fração com a cor", "unit": "fraction", "range": [0.0, 1.0], "limits": {"min": "min_fraction", "max": "max_fraction"}, "direction": "between", "level": 1}
    assert color[2]["direction"] == "at_most" and color[2]["limits"] == {"max": "max_gap"}
    english = client.get("/api/tools", headers={**headers, "Accept-Language": "en"}).json()["tools"]
    assert next(t for t in english if t["name"] == "color")["criteria"][0]["label"] == "Fraction with the colour"
    assert all(t["criteria"] == [] for t in client.get("/api/tools", headers=headers).json()["locators"])
