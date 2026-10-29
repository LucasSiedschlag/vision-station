"""A group of tools in the result as the API, the records and the overlay give it (TD-33, VIA-0137)."""

import numpy as np

from vision_station.api import schemas as m
from vision_station.api.app import _result
from vision_station.core.results import GroupReport, InspectionResult, Outcome, ReasonCode, ToolReport, contract_dict
from vision_station.pipeline import draw_overlay

RED = (50, 50, 230)


def _result_with_group(*, group_passed: bool) -> InspectionResult:
    tools = (
        ToolReport("a", "code", 1, group_passed, 1.0 if group_passed else 0.0, group="marca"),
        ToolReport("b", "code", 1, False, 0.0, group="marca"),
    )
    codes = () if group_passed else (ReasonCode("a", "code.min_count"), ReasonCode("b", "code.min_count"))
    regions = [
        {"tool": "a", "roi": "x", "rect": [10, 10, 40, 40], "passed": group_passed, "affects_result": True, "group": "marca"},
        {"tool": "b", "roi": "y", "rect": [60, 10, 90, 40], "passed": False, "affects_result": True, "group": "marca"},
    ]
    return InspectionResult(
        Outcome.PASS if group_passed else Outcome.FAIL, "" if group_passed else "Sem o lote", scores={"a": 1.0, "b": 0.0},
        details={"regions": regions}, reason_codes=codes, tools=tools, groups=(GroupReport("marca", group_passed, ("a", "b")),),
    )


def test_the_contract_carries_the_group_of_each_tool_and_the_groups():
    c = contract_dict(_result_with_group(group_passed=True))
    assert c["groups"] == [{"id": "marca", "passed": True, "members": ["a", "b"]}]
    assert [t["group"] for t in c["tools"]] == ["marca", "marca"]
    assert contract_dict(InspectionResult(Outcome.PASS))["groups"] == []


def test_the_api_result_has_the_groups_and_the_group_of_each_tool():
    out = _result(_result_with_group(group_passed=False))
    assert [(g.id, g.passed, g.members) for g in out.groups] == [("marca", False, ["a", "b"])]
    assert [t.group for t in out.tools] == ["marca", "marca"]
    assert m.ResultOut.model_validate(out.model_dump(mode="json")).groups[0].id == "marca"
    assert _result(InspectionResult(Outcome.PASS)).groups == []  # older clients and records: no group, no change


def test_a_member_that_did_not_match_is_not_drawn_as_a_failure_when_its_group_passed():
    image = np.full((60, 100, 3), 200, np.uint8)
    ok = draw_overlay(image, _result_with_group(group_passed=True))
    assert not (ok == np.array(RED, np.uint8)).all(axis=2).any()  # nothing in the colour of a failure
    bad = draw_overlay(image, _result_with_group(group_passed=False))
    assert (bad == np.array(RED, np.uint8)).all(axis=2).any()  # a failed group draws its members as failed


def test_a_record_read_through_the_api_has_the_groups(tmp_path):
    from vision_station.api.app import _record
    from vision_station.records import ResultStore

    with ResultStore(tmp_path) as store:
        rec = store.get(store.record(_result_with_group(group_passed=False), None, job_id="j", job_name="J", job_version=1).id)
        out = _record(rec)
    assert [(g.id, g.passed, g.members) for g in out.groups] == [("marca", False, ["a", "b"])]
    assert [t.group for t in out.tools] == ["marca", "marca"]
