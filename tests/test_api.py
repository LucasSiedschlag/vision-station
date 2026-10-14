import json

import numpy as np
import pytest
from fastapi.testclient import TestClient

from test_records import JOB, frame, res
from test_station import Rig, State, empty_scene, scene_with_box
from test_verification import inspect_code, make_bundle as job_bundle
from vision_station.api import ApiDeps, AuthError, AuthService, LockedOut, create_app, make_event_handler
from vision_station.records import RecordingConfig, ResultRecorder, ResultStore
from vision_station.results import InspectionResult, Outcome
from vision_station.store import JobRef, JobStore

HOSTS = ("testserver", "localhost", "127.0.0.1")


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


@pytest.fixture
def env(tmp_path):
    rig = Rig()
    jobs = JobStore(tmp_path / "data")
    results = ResultStore(tmp_path / "data")
    auth_clock = Clock()
    auth = AuthService(tmp_path / "data" / "system" / "users.json", clock=auth_clock)
    auth.set_password("supervisor", "supervisor-pass")
    auth.set_password("maintainer", "maintainer-pass")
    recorder = ResultRecorder(results)
    deps = ApiDeps(
        controller=rig.controller,
        acquisition=rig.acq,
        jobs=jobs,
        results=results,
        auth=auth,
        inspect=inspect_code,
        recorder=recorder,
        backup_dir=tmp_path / "backups",
        allowed_hosts=HOSTS,
        heartbeat_s=0.2,
        frame_fps=50,
    )
    rig.controller._on_event = make_event_handler(deps)
    rig.boot()
    client = TestClient(create_app(deps))
    yield type("Env", (), dict(rig=rig, jobs=jobs, results=results, auth=auth, clock=auth_clock, deps=deps, client=client, recorder=recorder))
    results.close()


def login(env, role="supervisor", password=None):
    r = env.client.post("/login", json={"role": role, "password": password or f"{role}-pass"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


# --- operator ----------------------------------------------------------------


def test_state_shows_the_station_the_job_the_camera_and_the_counters(env):
    body = env.client.get("/state").json()
    assert body["state"] == "Ready" and body["message"] == "Aguardando objeto"
    assert body["job"]["name"] == "Caixa M — fita vermelha" and body["job"]["version"] == 7 and body["job"]["id"]
    assert body["camera"]["connected"] is True and body["camera"]["last_frame_age_s"] is not None
    assert body["counters"] == {"PASS": 0, "FAIL": 0, "ERROR": 0, "total": 0}
    assert body["last_result"] is None and body["recording_failures"] == 0


def run_one_box(env):
    env.rig.camera.scene = scene_with_box(40)
    env.rig.tick(10)


def test_a_result_shows_in_state_last_result_counters_and_is_recorded(env):
    run_one_box(env)
    state = env.client.get("/state").json()
    assert state["state"] == "ShowingResult" and state["message"].startswith("PASS")
    assert state["counters"]["PASS"] == 1 and state["counters"]["total"] == 1
    assert state["last_record_id"] == env.recorder.last_record_id  # a screen opened now can still mark it wrong
    last = env.client.get("/result/last").json()
    assert last["outcome"] == "PASS" and last["record_id"] == env.recorder.last_record_id
    assert env.results.get(last["record_id"]).job_version == 7


def test_no_result_yet_is_a_404(env):
    assert env.client.get("/result/last").status_code == 404


def test_snapshot_is_a_jpeg(env):
    r = env.client.get("/snapshot.jpg")
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg" and r.content[:2] == b"\xff\xd8"


def test_manual_trigger_only_when_the_station_is_ready(env):
    assert env.client.post("/trigger").status_code == 202
    env.rig.tick(3)
    assert len(env.rig.inspected) == 1
    env.rig.camera.scene = scene_with_box(40)  # an object stays on the scale: the result stays on screen
    env.rig.tick(15)
    assert env.rig.state is State.SHOWING_RESULT
    assert env.client.post("/trigger").status_code == 409
    env.rig.camera.scene = empty_scene()
    env.rig.tick(6)
    env.rig.controller.pause()
    env.rig.tick(40)
    assert env.client.post("/trigger").status_code == 409


def test_the_operator_can_mark_a_result_as_wrong_without_logging_in(env):
    run_one_box(env)
    rid = env.recorder.last_record_id
    r = env.client.post(f"/results/{rid}/incorrect", json={"correct": "FAIL", "by": "operador"})
    assert r.status_code == 200 and r.json()["correct_outcome"] == "FAIL"
    assert env.client.post("/results/nope/incorrect", json={"correct": "FAIL"}).status_code == 404
    assert env.client.post(f"/results/{rid}/incorrect", json={"correct": "MAYBE"}).status_code == 400


# --- live view ---------------------------------------------------------------


def test_live_sends_the_status_then_frames_and_events(env):
    with env.client.websocket_connect("/live") as ws:
        first = ws.receive_json()
        assert first["type"] == "status" and first["state"] == "Ready"
        frame_bytes = ws.receive_bytes()
        assert frame_bytes[:2] == b"\xff\xd8"
        env.rig.camera.scene = scene_with_box(40)
        seen = []
        for _ in range(60):
            if not (len(seen) and any(m.get("type") == "result" for m in seen)):
                env.rig.tick(1)
            message = ws.receive()
            if "text" in message and message["text"]:
                seen.append(json.loads(message["text"]))
            if any(m.get("type") == "result" for m in seen):
                break
        types = [m["type"] for m in seen]
        assert "state" in types and "result" in types
        result = next(m for m in seen if m["type"] == "result")
        assert result["outcome"] == "PASS" and result["job"]["version"] == 7 and result["record_id"]
        states = [m["state"] for m in seen if m["type"] == "state"]
        assert "WaitingStill" in states and "Inspecting" in states


def test_live_frames_are_reduced_to_the_configured_rate_and_width(env):
    env.deps.frame_fps = 10
    env.deps.frame_width = 80
    import cv2

    with env.client.websocket_connect("/live") as ws:
        ws.receive_json()
        data = ws.receive_bytes()
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    assert img.shape[1] == 80  # the fake scene is 160 wide


def test_the_hub_drops_clients_that_left(env):
    with env.client.websocket_connect("/live") as ws:
        ws.receive_json()
        assert env.deps.hub.clients == 1
    for _ in range(20):
        if env.deps.hub.clients == 0:
            break
        env.rig.tick(1)
        import time

        time.sleep(0.05)
    assert env.deps.hub.clients == 0


# --- login and roles -----------------------------------------------------------


def test_protected_endpoints_need_a_login_and_the_right_role(env):
    for method, url in [("get", "/jobs"), ("get", "/results"), ("get", "/results.csv"), ("post", "/backup"), ("post", f"/collection/{JOB['job_id']}")]:
        assert getattr(env.client, method)(url, **({"json": {"enabled": True}} if "collection" in url else {})).status_code == 401, url
    sup = login(env, "supervisor")
    assert env.client.get("/jobs", headers=sup).status_code == 200
    assert env.client.post(f"/collection/{JOB['job_id']}", json={"enabled": True}, headers=sup).status_code == 403  # maintainer only
    assert env.client.post("/station/pause", headers=sup).status_code == 403
    mnt = login(env, "maintainer")
    assert env.client.post(f"/collection/{JOB['job_id']}", json={"enabled": True}, headers=mnt).status_code == 200
    assert env.client.get("/jobs", headers=mnt).status_code == 200  # a maintainer can do what a supervisor can
    assert env.client.get("/whoami", headers=mnt).json() == {"role": "maintainer"}
    assert env.client.get("/whoami").json() == {"role": "operator"}


def test_login_failures_logout_and_expiry(env):
    assert env.client.post("/login", json={"role": "supervisor", "password": "nope"}).status_code == 401
    assert env.client.post("/login", json={"role": "operator", "password": "x"}).status_code == 401
    sup = login(env)
    env.client.post("/logout", headers=sup)
    assert env.client.get("/jobs", headers=sup).status_code == 401
    sup = login(env)
    env.clock.now += 9 * 3600  # past the 8 h session
    assert env.client.get("/jobs", headers=sup).status_code == 401
    assert env.client.get("/jobs", headers={"Authorization": "Bearer made-up"}).status_code == 401


def test_repeated_wrong_passwords_lock_the_role_for_a_while(env):
    for _ in range(5):
        env.client.post("/login", json={"role": "supervisor", "password": "wrong"})
    locked = env.client.post("/login", json={"role": "supervisor", "password": "supervisor-pass"})
    assert locked.status_code == 429 and int(locked.headers["Retry-After"]) >= 1
    assert env.client.post("/login", json={"role": "maintainer", "password": "maintainer-pass"}).status_code == 200  # other roles unaffected
    env.clock.now += 31
    assert env.client.post("/login", json={"role": "supervisor", "password": "supervisor-pass"}).status_code == 200


def test_passwords_are_stored_hashed_and_must_be_long_enough(env, tmp_path):
    text = (tmp_path / "data" / "system" / "users.json").read_text()
    assert "supervisor-pass" not in text and "maintainer-pass" not in text and '"hash"' in text
    with pytest.raises(AuthError, match="at least"):
        env.auth.set_password("supervisor", "short")
    with pytest.raises(AuthError):
        env.auth.set_password("operator", "long-enough-password")
    sup = login(env)
    env.auth.set_password("supervisor", "a-new-password")
    assert env.client.get("/jobs", headers=sup).status_code == 401  # a new password ends the old sessions
    assert env.client.post("/login", json={"role": "supervisor", "password": "supervisor-pass"}).status_code == 401
    assert env.client.post("/login", json={"role": "supervisor", "password": "a-new-password"}).status_code == 200


def test_without_a_password_set_a_role_cannot_log_in(tmp_path):
    auth = AuthService(tmp_path / "users.json")
    assert not auth.has_password("supervisor")
    with pytest.raises(AuthError):
        auth.login("supervisor", "anything-at-all")


# --- local only ----------------------------------------------------------------


def test_other_hosts_and_other_origins_are_refused(env):
    assert env.client.get("/state", headers={"Host": "evil.example.com"}).status_code == 400
    assert env.client.get("/state", headers={"Origin": "http://evil.example.com"}).status_code == 403
    assert env.client.post("/trigger", headers={"Origin": "https://evil.example.com"}).status_code == 403
    assert env.client.get("/state", headers={"Origin": "http://localhost:8765"}).status_code == 200
    assert env.client.get("/state", headers={"Origin": "http://127.0.0.1:8765"}).status_code == 200
    with pytest.raises(Exception):
        with env.client.websocket_connect("/live", headers={"Origin": "http://evil.example.com"}) as ws:
            ws.receive_json()


# --- jobs ----------------------------------------------------------------------


def test_list_activate_export_and_import_jobs(env, tmp_path):
    sup = login(env)
    ref = env.jobs.save(job_bundle())
    listing = env.client.get("/jobs", headers=sup).json()
    assert listing["jobs"] == [{"id": ref.job_id, "name": "Etiqueta de lote", "versions": [1], "latest": 1}] and listing["active"] is None

    r = env.client.post(f"/jobs/{ref.job_id}/versions/1/activate", headers=sup, json={})
    assert r.status_code == 200 and r.json()["verified"] is True
    assert env.client.get("/jobs", headers=sup).json()["active"] == {"id": ref.job_id, "version": 1}
    env.rig.tick(5)
    assert env.client.get("/state").json()["job"]["name"] == "Etiqueta de lote"  # the station switched to it
    assert env.jobs.read_audit()[-1]["kind"] == "activate"

    exported = env.client.get(f"/jobs/{ref.job_id}/versions/1/export", headers=sup)
    assert exported.status_code == 200 and exported.content[:2] == b"PK"
    other = JobStore(tmp_path / "other")
    assert other.import_vjob(exported.content).ref == ref
    assert env.client.get("/jobs/nope/versions/1/export", headers=sup).status_code == 404


def test_importing_a_job_file_and_a_backup(env, tmp_path):
    sup = login(env)
    source = JobStore(tmp_path / "source")
    ref = source.save(job_bundle())
    source.set_active(ref)
    one = env.client.post("/jobs/import", content=source.export_vjob(ref), headers=sup)
    assert one.status_code == 200 and one.json()["kind"] == "job" and one.json()["imported"][0]["status"] == "added"
    backup = source.make_backup(tmp_path / "usb").read_bytes()
    both = env.client.post("/jobs/import", content=backup, headers=sup).json()
    assert both["kind"] == "backup" and both["imported"][0]["status"] == "already_present" and both["active_was"]["version"] == 1
    assert env.client.post("/jobs/import", content=b"junk", headers=sup).status_code == 400
    assert env.client.post("/jobs/import", content=b"junk").status_code == 401
    assert env.jobs.get_active() is None  # importing never activates


def test_activation_needs_a_verified_job_or_a_maintainers_override(env):
    ref = env.jobs.save(job_bundle())
    broken = env.jobs.save(job_bundle().__class__(job=job_bundle().job.model_copy(update={"job": job_bundle().job.job.model_copy(update={"version": 2, "parent_version": 1})}), profile=job_bundle().profile, extra={**job_bundle().extra, "tests/expected.yaml": b"cases:\n- {image: tests/images/blank.png, outcome: PASS}\n"}))
    sup, mnt = login(env), login(env, "maintainer")
    refused = env.client.post(f"/jobs/{ref.job_id}/versions/{broken.version}/activate", headers=sup, json={})
    assert refused.status_code == 409 and refused.json()["detail"]["verified"] is False and refused.json()["detail"]["problems"]
    assert env.jobs.get_active() is None
    assert env.client.post(f"/jobs/{ref.job_id}/versions/2/activate", headers=sup, json={"override_reason": "conferido a olho"}).status_code == 403
    done = env.client.post(f"/jobs/{ref.job_id}/versions/2/activate", headers=mnt, json={"override_reason": "conferido a olho"})
    assert done.status_code == 200 and done.json()["override"] is True
    assert env.jobs.read_audit()[-1]["kind"] == "activate_override"
    assert env.client.post(f"/jobs/{ref.job_id}/versions/9/activate", headers=sup, json={}).status_code == 404


def test_backup_is_made_in_the_configured_folder_and_downloaded(env):
    sup = login(env)
    env.jobs.save(job_bundle())
    made = env.client.post("/backup", headers=sup).json()
    assert made["name"].startswith("backup_") and made["size"] > 0
    got = env.client.get(f"/backup/{made['name']}", headers=sup)
    assert got.status_code == 200 and got.content[:2] == b"PK"
    assert env.client.get("/backup/..%2F..%2Fusers.json", headers=sup).status_code == 404
    assert env.client.get("/backup/other.vbak", headers=sup).status_code == 404
    env.deps.backup_dir = None
    assert env.client.post("/backup", headers=sup).status_code == 409


# --- results -------------------------------------------------------------------


def test_browse_filter_download_and_export_results(env):
    sup = login(env)
    store = env.results
    a = store.record(res(Outcome.FAIL, "Fita ausente"), frame(), overlay=frame(10), **JOB)
    store.record(res(), frame(), **JOB)
    body = env.client.get("/results?outcome=FAIL", headers=sup).json()
    assert body["total"] == 1 and body["results"][0]["id"] == a.id and body["results"][0]["reason"] == "Fita ausente"
    assert env.client.get("/results?limit=1", headers=sup).json()["total"] == 2
    assert env.client.get("/results?outcome=BAD", headers=sup).status_code == 422
    assert env.client.get(f"/results/{a.id}", headers=sup).json()["job_name"] == "Caixa M"
    assert env.client.get("/results/nope", headers=sup).status_code == 404
    image = env.client.get(f"/results/{a.id}/image", headers=sup)
    assert image.headers["content-type"] == "image/jpeg" and image.content[:2] == b"\xff\xd8"
    assert env.client.get(f"/results/{a.id}/image?overlay=true", headers=sup).status_code == 200
    csv = env.client.get("/results.csv?outcome=FAIL", headers=sup)
    assert csv.status_code == 200 and csv.content.startswith(b"\xef\xbb\xbf") and "Fita ausente" in csv.content.decode("utf-8-sig")
    assert env.client.get("/results").status_code == 401


def test_a_result_without_a_kept_image_has_no_image_endpoint(env):
    sup = login(env)
    r = env.results.record(res(Outcome.ERROR, "Câmera desconectada"), None, **JOB)
    assert env.client.get(f"/results/{r.id}/image", headers=sup).status_code == 404


# --- maintainer ----------------------------------------------------------------


def test_collection_mode_and_station_commands(env):
    mnt = login(env, "maintainer")
    r = env.client.post(f"/collection/{JOB['job_id']}", json={"enabled": True}, headers=mnt).json()
    assert r["enabled"] is True and env.results.collecting(JOB["job_id"])
    assert env.client.post("/station/pause", headers=mnt).json() == {"sent": "pause"}
    env.rig.tick(2)
    assert env.rig.state is State.PAUSED
    assert env.client.post("/station/resume", headers=mnt).status_code == 200
    env.rig.tick(5)
    assert env.rig.state is State.READY
    assert env.client.post("/station/explode", headers=mnt).status_code == 404


# --- the screens -----------------------------------------------------------------


def test_the_page_and_its_files_are_served_and_the_import_map_points_at_real_files(env):
    import re
    from vision_station.api.app import WEB_DIR

    page = env.client.get("/")
    assert page.status_code == 200 and page.headers["content-type"].startswith("text/html")
    assert page.headers["cache-control"] == "no-cache" and page.headers["x-content-type-options"] == "nosniff"
    html = page.text
    imports = json.loads(re.search(r'<script type="importmap">(.*?)</script>', html, re.S).group(1))["imports"]
    for name, url in imports.items():
        assert env.client.get(url).status_code == 200, f"{name} -> {url}"
    for url in re.findall(r'(?:href|src)="(/static/[^"]+)"', html):
        assert env.client.get(url).status_code == 200, url
    # every module the screens import exists
    for js in (WEB_DIR / "static").rglob("*.js"):
        if "vendor" in js.parts:
            continue
        for rel in re.findall(r"from '(\.{1,2}/[^']+)'", js.read_text(encoding="utf-8")):
            assert (js.parent / rel).resolve().is_file(), f"{js.name} imports {rel}"
    assert env.client.get("/static/../index.html").status_code in (404, 200)  # no path outside static (checked below)
    assert env.client.get("/static/%2e%2e/api/app.py").status_code == 404


def test_the_content_security_policy_allows_only_this_server_and_the_one_import_map(env):
    import base64, hashlib, re
    from vision_station.api.app import WEB_DIR

    csp = env.client.get("/").headers["content-security-policy"]
    html = (WEB_DIR / "index.html").read_text(encoding="utf-8")
    inline = re.search(r'<script type="importmap">(.*?)</script>', html, re.S).group(1)
    digest = base64.b64encode(hashlib.sha256(inline.encode()).digest()).decode()
    assert f"script-src 'self' 'sha256-{digest}'" in csp
    assert "default-src 'self'" in csp and "frame-ancestors 'none'" in csp and "unsafe-eval" not in csp
    assert "script-src 'self' 'unsafe-inline'" not in csp
    assert env.client.get("/state").headers["content-security-policy"] == csp
