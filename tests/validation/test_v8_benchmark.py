"""V8: every type is timed at the standard sizes and has a budget (architecture §15.3). CI only checks that it runs
and that the budget is declared: the time itself is judged by `vision-station --benchmark` on the real PC."""

import math

import pytest

from validation.registry import entries
from vision_station.system.benchmark import BenchmarkSettings, key, run_benchmark

SETTINGS = BenchmarkSettings()


@pytest.mark.parametrize("kind,name,version", entries("V8"))
def test_the_type_is_timed_at_every_size_and_has_a_budget_for_both_tiers(kind, name, version):
    item = key(kind, name, version)
    report = run_benchmark(BenchmarkSettings(repeats=1), types=[item])
    assert [m["type"] for m in report["measured"]] == [item], f"{item} cannot be timed: {[u['reason'] for u in report['unmeasured']]}"
    assert set(report["measured"][0]["ms"]) == {str(mp) for mp in SETTINGS.megapixels}
    assert all(math.isfinite(ms) and ms >= 0 for ms in report["measured"][0]["ms"].values())
    for tier in ("M", "R"):
        assert item in SETTINGS.budgets_ms[tier], f"{item} has no budget for tier {tier}"
