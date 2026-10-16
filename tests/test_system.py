import time
from datetime import datetime, timedelta

import cv2
import pytest
from fastapi.testclient import TestClient

from test_verification import make_bundle, qr_scene
from vision_station.api import create_app
from vision_station.pipeline import inspect_job
from vision_station.runtime import build_runtime, main
from vision_station.station import State
from vision_station.station.controller import NO_JOB
from vision_station.store import JobRef, JobStore
from vision_station.system import (
    ConfigError,
    Maintenance,
    SystemConfig,
    SystemService,
    changed_sections,
    check_camera,
    check_folder,
    config_path,
    load_config,
    parse_config,
    save_config,
    shift_start,
)
from vision_station.system.config import CameraSettings
from vision_station.verification import activate, verify_job

HOSTS = ("testserver", "localhost", "127.0.0.1")


# --- system.yaml -------------------------------------------------------------------------------------


def test_missing_file_means_defaults_and_a_saved_file_reads_back(tmp_path):
    assert load_config(tmp_path) == SystemConfig()
    config = SystemConfig.model_validate({"station": {"name": "Linha 2", "shift_starts": ["14:00", "06:00"]}, "camera": {"driver": "file", "connection": {"path": "imgs"}}})
    save_config(tmp_path, config)
    assert config_path(tmp_path).is_file() and not list(config_path(tmp_path).parent.glob(".system.yaml.*"))
    loaded = load_config(tmp_path)
    assert loaded == config and loaded.station.shift_starts == ["06:00", "14:00"]


@pytest.mark.parametrize(
    "text, where",
    [
        ("station: [unclosed", "not valid"),
        ("camera: {driver: firewire}", "unknown camera driver"),
        ("camera: {driver: uvc, connection: {password: abc}}", "secret"),
        ("station: {shift_starts: ['25:00']}", "HH:MM"),
        ("recording: {pass_sample_every: 0}", "pass_sample_every"),
        ("camera: {settle_ms: -1}", "settle_ms"),
        ("camera: {dead_after_s: -1}", "dead_after_s"),
        ("station: {result_min_s: -1}", "result_min_s"),
        ("colour: blue", "colour"),
    ],
)
def test_a_bad_file_is_an_error_that_says_where(text, where):
    with pytest.raises(ConfigError, match=where):
        parse_config(text)


def test_recording_and_shift_settings():
    config = SystemConfig.model_validate({"recording": {"pass_sample_every": 20, "retention_days": 90, "min_free_gb": 10}, "station": {"shift_starts": ["06:00", "14:00", "22:00"]}})
    rec = config.recording.to_recording_config()
    assert rec.pass_sample_every == 20 and rec.retention_days == 90 and rec.min_free_bytes == 10 * 1024**3
    day = datetime(2026, 10, 15, 0, 0).astimezone()
    assert shift_start(config, day.replace(hour=15, minute=30)) == day.replace(hour=14)
    assert shift_start(config, day.replace(hour=3)) == day.replace(hour=22) - timedelta(days=1)  # the night shift began yesterday
    assert shift_start(SystemConfig(), day.replace(hour=9)) == day


def test_the_camera_settling_time_reaches_the_acquisition(tmp_path):
    assert SystemConfig().camera.settle_ms == 500 and SystemConfig().camera.dead_after_s == 2.0
    root = tmp_path / "data"
    camera = {"driver": "file", "connection": {"path": str(tmp_path)}, "settle_ms": 200, "dead_after_s": 3.0}
    save_config(root, SystemConfig.model_validate({"camera": camera}))
    runtime = build_runtime(root, web_dist=tmp_path / "no-build")
    assert runtime.acquisition.settle_s == pytest.approx(0.2) and runtime.acquisition.dead_after_s == pytest.approx(3.0)


def test_the_minimum_time_of_a_verdict_reaches_the_controller_and_applies_without_a_restart(tmp_path):
    assert SystemConfig().station.result_min_s == 2.0
    root = tmp_path / "data"
    save_config(root, SystemConfig.model_validate({"camera": {"driver": "file", "connection": {"path": str(tmp_path)}}, "station": {"result_min_s": 3.5}}))
    runtime = build_runtime(root, web_dist=tmp_path / "no-build")
    assert runtime.controller._hold_s == pytest.approx(3.5)
    changed = runtime.system.config.model_copy(update={"station": runtime.system.config.station.model_copy(update={"result_min_s": 1.0})})
    assert runtime.system.update(changed) == ["station"] and runtime.system.restart_pending == []
    assert runtime.controller._hold_s == pytest.approx(1.0)


def test_changed_sections():
    a = SystemConfig()
    b = a.model_copy(update={"camera": CameraSettings(driver="file", connection={"path": "x"})})
    assert changed_sections(a, b) == ["camera"] and changed_sections(a, a) == []


# --- service and chores ------------------------------------------------------------------------------


def test_update_saves_applies_and_says_what_needs_a_restart(tmp_path):
    applied = []
    svc = SystemService(tmp_path, SystemConfig(), on_apply=applied.append)
    new = SystemConfig.model_validate({"recording": {"pass_sample_every": 5}})
    assert svc.update(new) == ["recording"] and applied == [new] and svc.restart_pending == []
    assert load_config(tmp_path) == new
    moved = new.model_copy(update={"camera": CameraSettings(driver="file", connection={"path": "x"})})
    assert svc.update(moved) == ["camera"] and svc.restart_pending == ["camera"]
    assert svc.update(moved) == [] and len(applied) == 2  # nothing changed, nothing applied
    assert svc.backup_dir() == tmp_path / "backups"


def test_check_folder(tmp_path):
    ok = check_folder(str(tmp_path / "bk"))
    assert ok.ok and ok.free_gb is not None and not list((tmp_path / "bk").iterdir())
    (tmp_path / "file").write_text("x")
    bad = check_folder(str(tmp_path / "file"))
    assert not bad.ok and bad.message.startswith("Não foi possível gravar")


def test_check_camera_with_the_file_driver(tmp_path):
    cv2.imwrite(str(tmp_path / "a.png"), qr_scene("X-1"))
    ok = check_camera(CameraSettings(driver="file", connection={"path": str(tmp_path)}))
    assert ok.ok and (ok.width, ok.height) == (320, 240)
    assert not check_camera(CameraSettings(driver="file", connection={"path": str(tmp_path / "none")})).ok
    assert not check_camera(CameraSettings(driver="file", connection={})).ok


class Clock:
    def __init__(self):
        self.now = datetime(2026, 10, 15, 8, 0).astimezone()

    def __call__(self):
        return self.now


def test_automatic_backup_when_due_and_failures_retried_every_15_minutes(tmp_path):
    jobs = JobStore(tmp_path / "data")
    from vision_station.records import ResultStore

    results = ResultStore(tmp_path / "data")
    svc = SystemService(tmp_path / "data", SystemConfig.model_validate({"backup": {"folder": str(tmp_path / "bk"), "every_hours": 24}}))
    clock = Clock()
    chores = Maintenance(svc, jobs, results, clock=clock)
    chores.tick()
    assert not (tmp_path / "bk").exists()  # nothing to back up yet
    jobs.save(make_bundle())
    chores.tick()
    assert len(list((tmp_path / "bk").glob("backup_*.vbak"))) == 1
    chores.tick()
    assert len(list((tmp_path / "bk").glob("backup_*.vbak"))) == 1  # not due again
    assert [a["kind"] for a in jobs.read_audit()].count("backup") == 1

    (tmp_path / "blocked").write_text("not a folder")
    svc.update(svc.config.model_copy(update={"backup": svc.config.backup.model_copy(update={"folder": str(tmp_path / "blocked")})}))
    chores.tick()
    chores.tick()
    assert chores.last_backup_error and [a["kind"] for a in jobs.read_audit()].count("backup_failed") == 1
    clock.now += timedelta(minutes=16)
    chores.tick()
    assert [a["kind"] for a in jobs.read_audit()].count("backup_failed") == 2
    results.close()


# --- the program ------------------------------------------------------------------------------------


def wait_for(predicate, timeout=10.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if predicate():
            return True
        time.sleep(0.05)
    return False


@pytest.fixture
def station(tmp_path):
    frames = tmp_path / "frames"
    frames.mkdir()
    cv2.imwrite(str(frames / "a.png"), qr_scene("LOTE-1"))
    root = tmp_path / "data"
    save_config(root, SystemConfig.model_validate({"camera": {"driver": "file", "connection": {"path": str(frames), "loop": True, "fps": 30}}, "backup": {"every_hours": None}}))
    runtime = build_runtime(root, web_dist=tmp_path / "no-build")
    runtime.deps.allowed_hosts = HOSTS
    runtime.auth.set_password("supervisor", "supervisor-pass")
    runtime.auth.set_password("maintainer", "maintainer-pass")
    yield runtime
    runtime.stop()


def login(client, role):
    r = client.post("/api/login", json={"role": role, "password": f"{role}-pass"})
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_without_an_active_job_the_screen_says_so(station):
    station.start(maintenance_period_s=3600)
    assert wait_for(lambda: station.acquisition.connected)
    status = station.controller.status()
    assert status.state is State.STARTING and status.message == NO_JOB


def test_the_active_job_is_loaded_verified_and_inspects(station):
    ref = station.jobs.save(make_bundle())
    activate(station.jobs, ref, verify_job(station.jobs.load(ref), inspect=inspect_job, parts="decision"))
    station.start(maintenance_period_s=3600)
    assert wait_for(lambda: station.controller.state not in (State.STARTING, State.PREPARING)), station.controller.status()
    assert station.controller.state is not State.FAULT, station.controller.status().detail
    station.controller.request_trigger()
    assert wait_for(lambda: station.controller.last_result is not None)
    assert station.controller.last_result.outcome.value == "PASS"


def test_a_real_inspection_is_listed_in_the_results_with_the_time_of_each_tool(station):
    """VIA-0046: the pipeline's timings carry the time of each tool; the results API gave 500 on them."""
    ref = station.jobs.save(make_bundle())
    activate(station.jobs, ref, verify_job(station.jobs.load(ref), inspect=inspect_job, parts="decision"))
    station.start(maintenance_period_s=3600)
    assert wait_for(lambda: station.controller.state is State.READY), station.controller.status()
    station.controller.request_trigger()
    assert wait_for(lambda: station.deps.recorder.last_record_id is not None)
    client = TestClient(create_app(station.deps))
    sup = login(client, "supervisor")
    listed = client.get("/api/results", headers=sup)
    assert listed.status_code == 200, listed.text
    record = listed.json()["results"][0]
    assert all(isinstance(v, float) for v in record["timings"].values()) and "total" in record["timings"]
    tool = make_bundle().job.tools[0].id
    assert set(record["tool_timings"]) == {tool}
    assert client.get(f"/api/results/{record['id']}", headers=sup).json()["tool_timings"] == record["tool_timings"]


def test_a_damaged_active_job_is_a_fault_with_the_reason(station):
    station.jobs.save(make_bundle())
    station.jobs.set_active(JobRef(str(make_bundle().job.job.id), 1))
    damaged = station.root / "jobs" / str(make_bundle().job.job.id) / "v1" / "job.yaml"
    damaged.chmod(0o644)  # saved versions are read-only
    damaged.write_text("broken: [", encoding="utf-8")
    station.start(maintenance_period_s=3600)
    assert wait_for(lambda: station.controller.state is State.FAULT)
    assert "não pôde ser carregado" in station.controller.status().detail


def test_system_api(station, tmp_path):
    client = TestClient(create_app(station.deps))
    sup, mnt = login(client, "supervisor"), login(client, "maintainer")
    assert client.get("/api/system").status_code == 401
    assert client.get("/api/system", headers=sup).status_code == 403
    body = client.get("/api/system", headers=mnt).json()
    assert body["config"]["camera"]["driver"] == "file" and body["restart_pending"] == [] and "file" in body["camera_drivers"]
    assert body["data_root"] == str(station.root)

    config = body["config"]
    config["recording"]["pass_sample_every"] = 10
    config["backup"]["folder"] = str(tmp_path / "bk")
    saved = client.put("/api/system", headers=mnt, json=config).json()
    assert saved == {"changed": ["recording", "backup"], "restart_required": []}
    assert station.results.config.pass_sample_every == 10 and station.deps.backup_dir == tmp_path / "bk"
    assert any(a["kind"] == "settings" and a["changed"] == ["recording", "backup"] and a["by"] == "maintainer" for a in station.jobs.read_audit())

    config["camera"]["connection"] = {"path": str(tmp_path / "elsewhere")}
    saved = client.put("/api/system", headers=mnt, json=config).json()
    assert saved["restart_required"] == ["camera"]
    assert client.get("/api/system", headers=mnt).json()["restart_pending"] == ["camera"]

    config["camera"]["connection"] = {"password": "x"}
    r = client.put("/api/system", headers=mnt, json=config)
    assert r.status_code == 422 and "secret" in r.text

    backup = client.post("/api/backup", headers=sup).json()
    assert backup["name"].endswith(".vbak")
    assert JobStore(tmp_path / "restored").restore_backup((tmp_path / "bk" / backup["name"]).read_bytes()).system_yaml is not None

    folder = client.post("/api/system/test-folder", headers=mnt, json={"path": str(tmp_path / "bk2")}).json()
    assert folder["ok"] and folder["free_gb"] is not None

    station.start(maintenance_period_s=3600)
    assert wait_for(lambda: station.acquisition.latest() is not None)
    running = client.post("/api/system/test-camera", headers=mnt, json=station.system.started_with.camera.model_dump()).json()
    assert running["ok"] and "em uso pela estação" in running["message"] and running["width"] == 320
    other = client.post("/api/system/test-camera", headers=mnt, json={"driver": "file", "connection": {"path": str(tmp_path / "none")}}).json()
    assert not other["ok"] and other["message"].startswith("A câmera não abriu")


def test_main_refuses_a_bad_config_and_an_open_network_without_passwords(tmp_path, capsys):
    root = tmp_path / "data"
    root.joinpath("system").mkdir(parents=True)
    config_path(root).write_text("camera: {driver: firewire}", encoding="utf-8")
    assert main(["--data", str(root)]) == 2
    save_config(root, SystemConfig.model_validate({"camera": {"driver": "file", "connection": {"path": str(tmp_path)}}, "network": {"host": "0.0.0.0"}}))
    assert main(["--data", str(root)]) == 2
