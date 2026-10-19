"""Limits proposed from the samples (FR-UI-14), and the batch test that feeds the gauges (document 05 §9.4, §19.3)."""

import pytest

from test_api import env, login  # noqa: F401
from test_manage_api import b64, draft, mnt  # noqa: F401
from test_verification import expected_yaml, make_bundle, no_code_scene, png, qr_scene
from vision_station.tools.limits import MARGIN, MIN_GOOD, propose_limit


# --- the pure rule -----------------------------------------------------------------------------------


def test_a_minimum_goes_in_the_middle_of_the_gap_and_the_margins_are_told():
    found = propose_limit("min", [0.80, 0.90, 0.95], [0.30, 0.52], "fraction")
    assert found.proposed == 0.66 and found.basis == "gap" and found.reason == ""
    assert found.worst_good == 0.80 and found.nearest_bad == 0.52
    assert found.margin_good == pytest.approx(0.14) and found.margin_bad == pytest.approx(0.14)


def test_a_maximum_is_the_same_the_other_way_round():
    found = propose_limit("max", [0.10, 0.20, 0.15], [0.60, 0.90], "fraction")
    assert found.proposed == 0.4 and found.worst_good == 0.20 and found.nearest_bad == 0.60


def test_samples_that_overlap_get_no_proposal_and_it_is_said():
    for good, bad in (([0.8, 0.9, 0.95], [0.85]), ([0.8, 0.9, 0.95], [0.8])):  # inside, and touching
        found = propose_limit("min", good, bad, "fraction")
        assert found.proposed is None and found.reason == "overlap"


def test_fewer_than_three_good_samples_propose_nothing():
    assert MIN_GOOD == 3
    assert propose_limit("min", [0.9, 0.95], [0.2], "fraction").reason == "few_good"


def test_with_no_bad_samples_the_limit_is_a_margin_from_the_worst_good_one():
    found = propose_limit("min", [0.80, 0.90, 0.95], [], "fraction")
    assert found.basis == "from_good" and found.proposed == pytest.approx(round(0.80 - MARGIN * 0.80, 2)) and found.margin_bad is None
    assert propose_limit("max", [0.10, 0.20, 0.15], [], "fraction").proposed == pytest.approx(0.24)
    # the worst good value is zero: the margin is not nothing
    assert propose_limit("max", [0.0, 0.0, 0.0], [], "fraction").proposed == pytest.approx(0.01)


def test_a_count_is_whole_and_on_the_right_side_of_the_gap():
    assert propose_limit("min", [1, 1, 2], [0], "count").proposed == 1  # the gap is 0..1: 1 passes the good ones, fails the bad
    assert propose_limit("max", [2, 2, 3], [5], "count").proposed == 4
    assert propose_limit("min", [3, 4, 4], [], "count").proposed == 3  # a count has no margin below the worst good one


def test_a_narrow_gap_is_written_with_the_decimals_it_needs():
    found = propose_limit("min", [0.8001, 0.9, 0.95], [0.7999], "fraction")
    assert 0.7999 < found.proposed <= 0.8001


def test_the_limit_stays_inside_what_the_parameter_accepts():
    # the least the parameter takes is above the worst good value: no limit can keep it passing
    assert propose_limit("min", [0.02, 0.03, 0.04], [], "fraction", bounds=(0.05, 1.0)).reason == "bounds"
    assert propose_limit("min", [0.5, 0.6, 0.7], [], "fraction", bounds=(0.45, 1.0)).proposed == 0.45  # clamped, still separates


# --- the batch test and the proposals through the API -----------------------------------------------


def with_samples(good=("LOTE-1", "LOTE-2", "LOTE-3"), bad=1):
    """A draft whose reference set has the given good samples (a code to read) and some with no code."""
    files = {name: data for name, data in make_bundle().extra.items() if not name.startswith("tests/")}
    cases = []
    for i, text in enumerate(good):
        files[f"tests/images/good{i}.png"] = png(qr_scene(text))
        cases.append({"image": f"tests/images/good{i}.png", "outcome": "PASS"})
    for i in range(bad):
        files[f"tests/images/bad{i}.png"] = png(no_code_scene())
        cases.append({"image": f"tests/images/bad{i}.png", "outcome": "FAIL"})
    files["tests/expected.yaml"] = expected_yaml(cases)
    body = draft()
    body["add_files"] = {name: b64(data) for name, data in files.items()}
    return body


def test_the_batch_runs_the_reference_and_every_sample_with_their_values(env, mnt):  # noqa: F811
    body = env.client.post("/api/editor/batch", headers=mnt, json=with_samples()).json()
    assert body["ok"] and [s["kind"] for s in body["samples"]] == ["reference", "good", "good", "good", "bad"]
    assert (body["good_total"], body["good_ok"], body["bad_total"], body["bad_ok"]) == (3, 3, 1, 1)
    reference = body["samples"][0]
    assert reference["image"] == "reference/reference.png" and reference["expected"] is None and reference["ok"]
    tool = reference["result"]["tools"][0]
    assert tool["id"] == "lote" and tool["values"]["matching"] == 1 and tool["units"]["matching"] == "count"
    assert body["samples"][-1]["result"]["tools"][0]["values"]["matching"] == 0
    assert body["tools"] == [{"tool": "lote", "good_total": 3, "good_passed": 3, "bad_total": 1, "bad_failed": 1}]
    assert body["max_ms"] >= 0


def test_the_reference_is_not_a_good_sample_and_a_job_without_samples_has_only_it(env, mnt):  # noqa: F811
    bare = draft()
    bare["add_files"] = {n: d for n, d in bare["add_files"].items() if not n.startswith("tests/")}
    body = env.client.post("/api/editor/batch", headers=mnt, json=bare).json()
    assert body["ok"] and [s["kind"] for s in body["samples"]] == ["reference"]
    assert body["good_total"] == 0 and body["tools"][0]["good_total"] == 0


def test_a_refused_draft_and_a_missing_login_are_answered(env, mnt):  # noqa: F811
    bad = draft()
    bad["job"]["tools"][0]["roi"] = "nowhere"
    out = env.client.post("/api/editor/batch", headers=mnt, json=bad).json()
    assert out["ok"] is False and out["samples"] == [] and out["message"]
    assert env.client.post("/api/editor/batch", json=draft()).status_code == 401
    assert env.client.post("/api/editor/batch", headers=login(env), json=draft()).status_code == 403
    assert env.client.post("/api/editor/suggest/limits", json={"draft": draft()}).status_code == 401


def test_the_proposal_puts_the_minimum_where_the_samples_separate(env, mnt):  # noqa: F811
    out = env.client.post("/api/editor/suggest/limits", headers=mnt, json={"draft": with_samples()}).json()
    assert out["ok"]
    [low] = [p for p in out["proposals"] if p["side"] == "min"]
    assert low["tool"] == "lote" and low["param"] == "min_count" and low["unit"] == "count"
    assert low["current"] == 1 and low["proposed"] == 1 and low["basis"] == "gap" and low["good_n"] == 3 and low["bad_n"] == 1
    assert low["worst_good"] == 1 and low["nearest_bad"] == 0 and low["label"] == "Códigos aceitos"
    [high] = [p for p in out["proposals"] if p["side"] == "max"]
    assert high["param"] == "max_count" and high["proposed"] == 1 and high["basis"] == "from_good"  # no bad sample above the good ones
    english = env.client.post("/api/editor/suggest/limits", headers={**mnt, "Accept-Language": "en"}, json={"draft": with_samples()}).json()
    assert english["proposals"][0]["label"] == "Codes accepted"


def test_few_samples_say_so_instead_of_inventing_a_limit(env, mnt):  # noqa: F811
    out = env.client.post("/api/editor/suggest/limits", headers=mnt, json={"draft": with_samples(good=("LOTE-1", "LOTE-2"))}).json()
    assert {p["reason"] for p in out["proposals"]} == {"few_good"} and all(p["proposed"] is None for p in out["proposals"])
    assert env.client.post("/api/editor/suggest/limits", headers=mnt, json={"draft": with_samples(), "tool": "other"}).json()["proposals"] == []


def test_a_bad_sample_that_another_tool_catches_does_not_make_this_gauge_overlap(env, mnt):  # noqa: F811
    """Two code tools on the same label: the second one always passes (it asks for nothing), the first one fails the
    sample with no code. The second tool's gauge would call it an overlap if the sample counted for it too."""
    body = with_samples()
    body["job"]["tools"].append({**body["job"]["tools"][0], "id": "extra", "params": {"min_count": 1, "max_count": 5}, "reason_fail": "x"})
    out = env.client.post("/api/editor/suggest/limits", headers=mnt, json={"draft": body, "tool": "extra"}).json()
    low = [p for p in out["proposals"] if p["side"] == "min"][0]
    assert low["reason"] != "overlap"
