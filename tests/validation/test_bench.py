"""The bench itself: every type has its case, and the exception table is honest (NFR-MAI-5)."""

import pytest

from validation.registry import CHECKS, EXCEPTIONS, TASK, TYPES, applies, case_for, entries


@pytest.mark.parametrize("kind,name,version", [pytest.param(*t, id=f"{t[0]}-{t[1]}-v{t[2]}") for t in TYPES])
def test_every_registered_type_has_its_validation_case(kind, name, version):
    case = case_for(kind, name, version)
    assert case is not None, f"{kind} {name} v{version} has no case in tests/validation/cases/{name}.py"
    if kind == "tool":
        assert case.passing is not None and case.failing is not None, f"{name} v{version}: needs a passing and a failing region"


def test_there_is_no_case_for_a_type_that_is_not_registered():
    from pathlib import Path

    known = {(k, n, v) for k, n, v in TYPES}
    for path in Path(__file__).with_name("cases").glob("[a-z]*.py"):
        import importlib

        module = importlib.import_module(f"validation.cases.{path.stem}")
        for kind, attr in (("tool", "TOOLS"), ("locator", "LOCATORS")):
            for version in getattr(module, attr, {}):
                assert (kind, path.stem, version) in known, f"{path.name}: {kind} v{version} is not registered"


def test_the_exceptions_name_a_real_type_a_real_check_and_a_task():
    known = set(TYPES)
    for (kind, name, version, check), task in EXCEPTIONS.items():
        assert (kind, name, version) in known, (kind, name, version)
        assert check.split('.')[0] in CHECKS and applies(kind, check), (name, check)
        assert TASK.fullmatch(task), f"{name} {check}: {task!r} is not a VIA task"


def test_a_listed_exception_is_a_strict_expected_failure():
    (param,) = [p for p in entries("V1", {("tool", "color", 1, "V1"): "VIA-0001"}) if p.values[1] == "color"]
    (mark,) = param.marks
    assert mark.name == "xfail" and mark.kwargs["strict"] is True and mark.kwargs["reason"] == "VIA-0001"
