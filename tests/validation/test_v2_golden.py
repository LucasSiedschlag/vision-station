"""V2: pictures with a known answer, checked to a tolerance (architecture §15.3)."""

import pytest

from validation.registry import case_for, entries
from vision_station.locators import run_locator
from vision_station.tools import run_tool


def _box(mark):
    xs, ys = [p[0] for p in mark.points], [p[1] for p in mark.points]
    return (min(xs), min(ys), max(xs), max(ys))


@pytest.mark.parametrize("kind,name,version", entries("V2"))
def test_the_known_answers_are_given(kind, name, version):
    case = case_for(kind, name, version)
    assert case.goldens, "no golden picture"
    for g in case.goldens:
        params, files = {**case.params, **g.params}, case.files if g.files is None else g.files
        if kind == "tool":
            result = run_tool(name, version, g.image, params, files)
            assert result.passed == g.passed, g.id
            for key, expected in g.values.items():
                if isinstance(expected, str):
                    assert result.values[key] == expected, f"{g.id}: {key}"
                else:
                    assert result.values[key] == pytest.approx(expected, abs=g.tolerance), f"{g.id}: {key}"
            if g.marks is not None:
                got = [(m.kind, m.role, _box(m)) for m in result.marks]
                assert [(k, r) for k, r, _ in got] == [(k, r) for k, r, _ in g.marks], f"{g.id}: marks {got}"
                for (_, _, box), (_, _, want) in zip(got, g.marks, strict=True):
                    assert box == pytest.approx(want, abs=g.mark_tolerance), f"{g.id}: mark box"
        else:
            fixture = run_locator(name, version, g.image, params, files)
            if g.rect is None:
                assert fixture is None, f"{g.id}: found something"
            else:
                assert fixture is not None, f"{g.id}: found nothing"
                assert fixture.rect == pytest.approx(g.rect, abs=g.tolerance), g.id
