"""V1: the parameter schema is labelled in both languages and invalid combinations are refused (architecture §15.3).
Levels, groups and gauges are checked by `tests/test_schema_meta.py`."""

import pytest

from validation.registry import case_for, entries
from vision_station.core.i18n import english, render_schema, using
from vision_station.core.schema_labels import USED
from vision_station.locators import LocatorError, get_locator, validate_params as validate_locator
from vision_station.tools import ToolError, get_tool, validate_params as validate_tool


def _entry(kind, name, version):
    return get_tool(name, version) if kind == "tool" else get_locator(name, version)


def _objects(schema):
    yield schema
    for definition in schema.get("$defs", {}).values():
        if "properties" in definition:
            yield definition


def _texts(schema):
    """Every text the form shows: titles, descriptions and the labels of the choices."""
    for obj in _objects(schema):
        if obj.get("description"):
            yield obj["description"]
        for prop in obj["properties"].values():
            for key in ("title", "description"):
                if prop.get(key):
                    yield prop[key]
            yield from prop.get("x-enum-labels", {}).values()


@pytest.mark.parametrize("kind,name,version", entries("V1"))
def test_every_parameter_is_titled_and_every_text_is_in_both_languages(kind, name, version):
    schema = _entry(kind, name, version).params.model_json_schema()
    for obj in _objects(schema):
        for field, prop in obj["properties"].items():
            assert prop.get("title") in USED, f"{name}.{field}: no title from `labels` (pydantic's default is not a translation)"
    catalog = english()
    missing = [text for text in _texts(schema) if text not in catalog]
    assert not missing, f"{name} v{version}: not in the English catalog: {missing}"
    with using("en"):
        in_english = render_schema(schema)
    assert in_english["description"] != schema["description"], f"{name}: the description is not translated"


@pytest.mark.parametrize("kind,name,version", entries("V1"))
def test_the_cases_parameters_are_valid_and_bad_combinations_are_refused(kind, name, version):
    case = case_for(kind, name, version)
    validate, error = (validate_tool, ToolError) if kind == "tool" else (validate_locator, LocatorError)
    validate(name, version, case.params)
    for bad in (*case.bad_params, {**case.params, "no_such_parameter": 1}):
        with pytest.raises(error):
            validate(name, version, bad)
