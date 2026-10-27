"""The built-in benchmark (FR-ADM-5, TD-28): classification, the stored report, the command and the settings file."""

import json

import pytest

from vision_station.runtime import main
from vision_station.system import ConfigError, SystemConfig, dump_config, parse_config
from vision_station.system.benchmark import classify, load_report, report_path, run_benchmark, save_report
from vision_station.system.config import BenchmarkSettings

FAST = BenchmarkSettings(megapixels=[0.25, 1.0], repeats=1)


def test_the_tier_follows_the_configured_thresholds():
    s = BenchmarkSettings(tier_r_max_ms=100, tier_m_max_ms=300)
    assert [classify(ms, s) for ms in (50, 100, 100.1, 300, 300.1)] == ["R", "R", "M", "M", None]


def test_a_clock_that_makes_every_run_take_a_fixed_time_gives_a_known_report():
    ticks = iter(range(10_000))
    report = run_benchmark(FAST, types=["tool:color:1"], clock=lambda: next(ticks) * 0.05)  # each run takes 50 ms
    assert report["measured"][0]["ms"] == {"0.25": 50.0, "1.0": 50.0}
    assert report["reference_ms"] == 50.0 and report["tier"] == "R"
    assert report["measured"][0]["within_budget"] is False and report["over_budget"] == ["tool:color:1"]  # 50 ms > the 25 ms of tier R


def test_a_pc_slower_than_tier_m_has_no_tier_and_is_judged_by_the_budget_of_m():
    slow = BenchmarkSettings(megapixels=[0.25, 1.0], repeats=1, tier_r_max_ms=1, tier_m_max_ms=2)
    ticks = iter(range(10_000))
    report = run_benchmark(slow, types=["tool:color:1"], clock=lambda: next(ticks) * 0.05)
    assert report["tier"] is None and report["measured"][0]["budget_ms"] == slow.budgets_ms["M"]["tool:color:1"]


def test_the_thread_limit_is_the_cap_of_the_tier_and_never_more_than_the_cpus(monkeypatch):
    monkeypatch.setattr("os.cpu_count", lambda: 2)
    assert run_benchmark(FAST, types=["tool:color:1"])["thread_limit"] == 2
    monkeypatch.setattr("os.cpu_count", lambda: 16)
    assert run_benchmark(FAST, types=["tool:color:1"])["thread_limit"] <= max(FAST.thread_caps.values())


def test_the_report_is_stored_and_read_back(tmp_path):
    assert load_report(tmp_path) is None
    report = run_benchmark(FAST, types=["locator:fixed:1"])
    path = save_report(tmp_path, report)
    assert path == report_path(tmp_path) and load_report(tmp_path) == json.loads(json.dumps(report))
    assert [p.name for p in path.parent.iterdir()] == ["benchmark.json"]  # no temp file left behind


def test_the_settings_are_a_section_of_system_yaml_written_only_when_changed():
    assert "benchmark" not in dump_config(SystemConfig())
    changed = SystemConfig(benchmark=BenchmarkSettings(tier_r_max_ms=80, repeats=3))
    back = parse_config(dump_config(changed))
    assert (back.benchmark.tier_r_max_ms, back.benchmark.repeats) == (80, 3)
    with pytest.raises(ConfigError):
        parse_config("benchmark: {tier_r_max_ms: 500}")  # above the limit of tier M


def _cpu(seconds_for_all_frames: float):
    """A CPU clock that says the timed frames took this long in all (it is read twice: before and after)."""
    ticks = iter([0.0, seconds_for_all_frames])
    return lambda: next(ticks)


def test_the_idle_trigger_is_judged_as_a_share_of_the_whole_pc_against_the_limit_of_the_tier(monkeypatch):
    monkeypatch.setattr("os.cpu_count", lambda: 2)
    settings = BenchmarkSettings(megapixels=[0.25, 1.0], repeats=1, idle_frames=40, idle_fps=30, idle_cpu_max_pct={"M": 35, "R": 15})
    # 40 frames in 0.4 s of CPU: 10 ms each, 30 per second = 30 % of one core = 15 % of two: at the limit of tier R
    report = run_benchmark(settings, types=["locator:fixed:1"], idle=True, cpu_clock=_cpu(0.4))
    idle = report["idle_trigger"]
    assert report["tier"] == "R" and (idle["ms_per_frame"], idle["cpu_pct_core"], idle["cpu_pct"], idle["limit_pct"]) == (10.0, 30.0, 15.0, 15.0)
    assert idle["within_limit"] is True
    # 20 ms each: 60 % of a core, 30 % of two: over the 15 % of tier R
    assert run_benchmark(settings, types=["locator:fixed:1"], idle=True, cpu_clock=_cpu(0.8))["idle_trigger"]["within_limit"] is False
    # a PC slower than tier M is judged by the limit of M (35 %), as its times are by the budgets of M
    slow = settings.model_copy(update={"tier_r_max_ms": 0.0001, "tier_m_max_ms": 0.0002})
    report = run_benchmark(slow, types=["tool:color:1"], idle=True, cpu_clock=_cpu(0.8))
    assert report["tier"] is None and report["idle_trigger"]["limit_pct"] == 35.0 and report["idle_trigger"]["within_limit"] is True


def test_the_idle_trigger_is_timed_in_the_full_run_and_only_when_asked_for_in_a_partial_one():
    assert run_benchmark(FAST, types=["locator:fixed:1"])["idle_trigger"] is None
    assert run_benchmark(FAST, types=["locator:fixed:1"], idle=True)["idle_trigger"]["ms_per_frame"] > 0


def test_the_summary_says_when_the_idle_trigger_is_over_its_limit(monkeypatch):
    from vision_station.system.benchmark import summary

    monkeypatch.setattr("os.cpu_count", lambda: 1)
    report = run_benchmark(FAST, types=["locator:fixed:1"], idle=True, cpu_clock=_cpu(0.8))  # 60 % of the only core
    assert "image trigger waiting" in summary(report) and "OVER THE LIMIT" in summary(report)


def test_the_idle_limits_are_settings_in_system_yaml():
    config = parse_config("benchmark: {idle_cpu_max_pct: {M: 40, R: 20}, idle_fps: 15}")
    assert config.benchmark.idle_cpu_max_pct == {"M": 40, "R": 20} and config.benchmark.idle_fps == 15
    with pytest.raises(ConfigError):
        parse_config("benchmark: {idle_cpu_max_pct: {M: 140, R: 20}}")


def test_the_command_runs_saves_the_report_and_says_the_tier(tmp_path, capsys):
    (tmp_path / "system").mkdir()
    (tmp_path / "system" / "system.yaml").write_text("benchmark: {megapixels: [0.25, 1.0], repeats: 1, tier_r_max_ms: 100000, tier_m_max_ms: 100000, budgets_ms: {M: {}, R: {}}}\n")
    assert main(["--benchmark", "--data", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "Tier: R" in out and "tool:code:1" in out and "not timed" in out and "image trigger waiting" in out
    assert load_report(tmp_path)["tier"] == "R"
