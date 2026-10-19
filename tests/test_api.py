import json
import re
from pathlib import Path

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from test_records import JOB, frame, res
from test_station import Rig, State, empty_scene, scene_with_object
from test_verification import inspect_code, make_bundle as job_bundle
from vision_station.api import ApiDeps, AuthError, AuthService, LockedOut, create_app, make_event_handler
from vision_station.records import RecordingConfig, ResultRecorder, ResultStore
from vision_station.core.results import InspectionResult, Outcome
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
        web_dist=tmp_path / "no-build",  # these tests do not depend on whether the interface was built
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
    r = env.client.post("/api/login", json={"role": role, "password": password or f"{role}-pass"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


# --- operator ----------------------------------------------------------------


def test_state_shows_the_station_the_job_the_camera_and_the_counters(env):
    body = env.client.get("/api/state").json()
    assert body["state"] == "Ready" and body["message"] == "Aguardando objeto"
    assert body["job"]["name"] == "Tampa azul — etiqueta de lote" and body["job"]["version"] == 7 and body["job"]["id"]
    assert body["camera"]["connected"] is True and body["camera"]["last_frame_age_s"] is not None
    assert body["counters"] == {"PASS": 0, "FAIL": 0, "ERROR": 0, "total": 0}
    assert body["last_result"] is None and body["recording_failures"] == 0


def run_one_box(env):
    env.rig.camera.scene = scene_with_object(40)
    env.rig.tick(10)


def test_a_result_shows_in_state_last_result_counters_and_is_recorded(env):
    run_one_box(env)
    state = env.client.get("/api/state").json()
    assert state["state"] == "ShowingResult" and state["message"].startswith("PASS")
    assert state["counters"]["PASS"] == 1 and state["counters"]["total"] == 1
    assert state["last_record_id"] == env.recorder.last_record_id  # a screen opened now can still mark it wrong
    assert [r["outcome"] for r in state["recent"]] == ["PASS"] and state["recent"][0]["at"] == state["last_result"]["at"]
    last = env.client.get("/api/result/last").json()
    assert last["outcome"] == "PASS" and last["record_id"] == env.recorder.last_record_id
    assert env.results.get(last["record_id"]).job_version == 7


def test_no_result_yet_is_a_404(env):
    assert env.client.get("/api/result/last").status_code == 404


def test_snapshot_is_a_jpeg(env):
    r = env.client.get("/api/snapshot.jpg")
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg" and r.content[:2] == b"\xff\xd8"


def test_manual_trigger_only_when_the_station_is_ready(env):
    assert env.client.post("/api/trigger").status_code == 202
    env.rig.tick(3)
    assert len(env.rig.inspected) == 1
    env.rig.camera.scene = scene_with_object(40)  # an object stays on the scale: the result stays on screen
    env.rig.tick(15)
    assert env.rig.state is State.SHOWING_RESULT
    assert env.client.post("/api/trigger").status_code == 409
    env.rig.camera.scene = empty_scene()
    env.rig.tick(6)
    env.rig.controller.pause()
    env.rig.tick(40)
    assert env.client.post("/api/trigger").status_code == 409


def test_the_operator_can_mark_a_result_as_wrong_without_logging_in(env):
    run_one_box(env)
    rid = env.recorder.last_record_id
    r = env.client.post(f"/api/results/{rid}/incorrect", json={"correct": "FAIL", "by": "operador"})
    assert r.status_code == 200 and r.json()["correct_outcome"] == "FAIL"
    assert env.client.post("/api/results/nope/incorrect", json={"correct": "FAIL"}).status_code == 404
    assert env.client.post(f"/api/results/{rid}/incorrect", json={"correct": "MAYBE"}).status_code == 422


# --- live view ---------------------------------------------------------------


def test_live_sends_the_status_then_frames_and_events(env):
    with env.client.websocket_connect("/api/live") as ws:
        first = ws.receive_json()
        assert first["type"] == "status" and first["state"] == "Ready"
        frame_bytes = ws.receive_bytes()
        assert frame_bytes[:2] == b"\xff\xd8"
        env.rig.camera.scene = scene_with_object(40)
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

    with env.client.websocket_connect("/api/live") as ws:
        ws.receive_json()
        data = ws.receive_bytes()
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    assert img.shape[1] == 80  # the fake scene is 160 wide


def test_the_hub_drops_clients_that_left(env):
    with env.client.websocket_connect("/api/live") as ws:
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
    for method, url in [("get", "/api/jobs"), ("get", "/api/results"), ("get", "/api/results.csv"), ("post", "/api/backup"), ("post", f"/api/collection/{JOB['job_id']}")]:
        assert getattr(env.client, method)(url, **({"json": {"enabled": True}} if "collection" in url else {})).status_code == 401, url
    sup = login(env, "supervisor")
    assert env.client.get("/api/jobs", headers=sup).status_code == 200
    assert env.client.post(f"/api/collection/{JOB['job_id']}", json={"enabled": True}, headers=sup).status_code == 403  # maintainer only
    assert env.client.post("/api/station/pause", headers=sup).status_code == 403
    mnt = login(env, "maintainer")
    assert env.client.post(f"/api/collection/{JOB['job_id']}", json={"enabled": True}, headers=mnt).status_code == 200
    assert env.client.get("/api/jobs", headers=mnt).status_code == 200  # a maintainer can do what a supervisor can
    assert env.client.get("/api/whoami", headers=mnt).json() == {"role": "maintainer"}
    assert env.client.get("/api/whoami").json() == {"role": "operator"}


def test_login_failures_logout_and_expiry(env):
    assert env.client.post("/api/login", json={"role": "supervisor", "password": "nope"}).status_code == 401
    assert env.client.post("/api/login", json={"role": "operator", "password": "x"}).status_code == 422  # only the two protected roles log in
    sup = login(env)
    env.client.post("/api/logout", headers=sup)
    assert env.client.get("/api/jobs", headers=sup).status_code == 401
    sup = login(env)
    env.clock.now += 9 * 3600  # past the 8 h session
    assert env.client.get("/api/jobs", headers=sup).status_code == 401
    assert env.client.get("/api/jobs", headers={"Authorization": "Bearer made-up"}).status_code == 401


def test_repeated_wrong_passwords_lock_the_role_for_a_while(env):
    for _ in range(5):
        env.client.post("/api/login", json={"role": "supervisor", "password": "wrong"})
    locked = env.client.post("/api/login", json={"role": "supervisor", "password": "supervisor-pass"})
    assert locked.status_code == 429 and int(locked.headers["Retry-After"]) >= 1
    assert env.client.post("/api/login", json={"role": "maintainer", "password": "maintainer-pass"}).status_code == 200  # other roles unaffected
    env.clock.now += 31
    assert env.client.post("/api/login", json={"role": "supervisor", "password": "supervisor-pass"}).status_code == 200


def test_passwords_are_stored_hashed_and_must_be_long_enough(env, tmp_path):
    text = (tmp_path / "data" / "system" / "users.json").read_text()
    assert "supervisor-pass" not in text and "maintainer-pass" not in text and '"hash"' in text
    with pytest.raises(AuthError, match="pelo menos"):
        env.auth.set_password("supervisor", "short")
    with pytest.raises(AuthError):
        env.auth.set_password("operator", "long-enough-password")
    sup = login(env)
    env.auth.set_password("supervisor", "a-new-password")
    assert env.client.get("/api/jobs", headers=sup).status_code == 401  # a new password ends the old sessions
    assert env.client.post("/api/login", json={"role": "supervisor", "password": "supervisor-pass"}).status_code == 401
    assert env.client.post("/api/login", json={"role": "supervisor", "password": "a-new-password"}).status_code == 200


def test_without_a_password_set_a_role_cannot_log_in(tmp_path):
    auth = AuthService(tmp_path / "users.json")
    assert not auth.has_password("supervisor")
    with pytest.raises(AuthError):
        auth.login("supervisor", "anything-at-all")


# --- local only ----------------------------------------------------------------


def test_other_hosts_and_other_origins_are_refused(env):
    assert env.client.get("/api/state", headers={"Host": "evil.example.com"}).status_code == 400
    assert env.client.get("/api/state", headers={"Origin": "http://evil.example.com"}).status_code == 403
    assert env.client.post("/api/trigger", headers={"Origin": "https://evil.example.com"}).status_code == 403
    assert env.client.get("/api/state", headers={"Origin": "http://localhost:8765"}).status_code == 200
    assert env.client.get("/api/state", headers={"Origin": "http://127.0.0.1:8765"}).status_code == 200
    with pytest.raises(Exception):
        with env.client.websocket_connect("/api/live", headers={"Origin": "http://evil.example.com"}) as ws:
            ws.receive_json()


# --- jobs ----------------------------------------------------------------------


def test_list_activate_export_and_import_jobs(env, tmp_path):
    sup = login(env)
    ref = env.jobs.save(job_bundle())
    listing = env.client.get("/api/jobs", headers=sup).json()
    assert listing["jobs"] == [{"id": ref.job_id, "name": "Etiqueta de lote", "versions": [1], "latest": 1, "updated_at": "2026-10-02T15:40:00-03:00", "author": "lucas"}] and listing["active"] is None

    r = env.client.post(f"/api/jobs/{ref.job_id}/versions/1/activate", headers=sup, json={})
    assert r.status_code == 200 and r.json()["verified"] is True
    assert env.client.get("/api/jobs", headers=sup).json()["active"] == {"id": ref.job_id, "version": 1}
    env.rig.tick(5)
    assert env.client.get("/api/state").json()["job"]["name"] == "Etiqueta de lote"  # the station switched to it
    assert env.jobs.read_audit()[-1]["kind"] == "activate"

    exported = env.client.get(f"/api/jobs/{ref.job_id}/versions/1/export", headers=sup)
    assert exported.status_code == 200 and exported.content[:2] == b"PK"
    other = JobStore(tmp_path / "other")
    assert other.import_vjob(exported.content).ref == ref
    assert env.client.get("/api/jobs/nope/versions/1/export", headers=sup).status_code == 404


def test_importing_a_job_file_and_a_backup(env, tmp_path):
    sup = login(env)
    source = JobStore(tmp_path / "source")
    ref = source.save(job_bundle())
    source.set_active(ref)
    one = env.client.post("/api/jobs/import", content=source.export_vjob(ref), headers=sup)
    assert one.status_code == 200 and one.json()["kind"] == "job" and one.json()["imported"][0]["status"] == "added"
    backup = source.make_backup(tmp_path / "usb").read_bytes()
    both = env.client.post("/api/jobs/import", content=backup, headers=sup).json()
    assert both["kind"] == "backup" and both["imported"][0]["status"] == "already_present" and both["active_was"]["version"] == 1
    assert env.client.post("/api/jobs/import", content=b"junk", headers=sup).status_code == 400
    assert env.client.post("/api/jobs/import", content=b"junk").status_code == 401
    assert env.jobs.get_active() is None  # importing never activates


def test_activation_needs_a_verified_job_or_a_maintainers_override(env):
    ref = env.jobs.save(job_bundle())
    broken = env.jobs.save(job_bundle().__class__(job=job_bundle().job.model_copy(update={"job": job_bundle().job.job.model_copy(update={"version": 2, "parent_version": 1})}), profile=job_bundle().profile, extra={**job_bundle().extra, "tests/expected.yaml": b"cases:\n- {image: tests/images/blank.png, outcome: PASS}\n"}))
    sup, mnt = login(env), login(env, "maintainer")
    refused = env.client.post(f"/api/jobs/{ref.job_id}/versions/{broken.version}/activate", headers=sup, json={})
    assert refused.status_code == 409 and refused.json()["code"] == "verification_failed" and refused.json()["verified"] is False and refused.json()["problems"]
    assert env.jobs.get_active() is None
    assert env.client.post(f"/api/jobs/{ref.job_id}/versions/2/activate", headers=sup, json={"override_reason": "conferido a olho"}).status_code == 403
    done = env.client.post(f"/api/jobs/{ref.job_id}/versions/2/activate", headers=mnt, json={"override_reason": "conferido a olho"})
    assert done.status_code == 200 and done.json()["override"] is True
    assert env.jobs.read_audit()[-1]["kind"] == "activate_override"
    assert env.client.post(f"/api/jobs/{ref.job_id}/versions/9/activate", headers=sup, json={}).status_code == 404


def test_backup_is_made_in_the_configured_folder_and_downloaded(env):
    sup = login(env)
    env.jobs.save(job_bundle())
    made = env.client.post("/api/backup", headers=sup).json()
    assert made["name"].startswith("backup_") and made["size"] > 0
    got = env.client.get(f"/api/backup/{made['name']}", headers=sup)
    assert got.status_code == 200 and got.content[:2] == b"PK"
    assert env.client.get("/api/backup/..%2F..%2Fusers.json", headers=sup).status_code == 404
    assert env.client.get("/api/backup/other.vbak", headers=sup).status_code == 404
    env.deps.backup_dir = None
    assert env.client.post("/api/backup", headers=sup).status_code == 409


# --- results -------------------------------------------------------------------


def test_a_result_picture_comes_small_for_everyone_and_the_recent_results_name_it(env):
    a = env.results.record(res(Outcome.FAIL, "Tampa ausente"), np.random.default_rng(1).integers(0, 255, (480, 640, 3), np.uint8), **JOB)
    recent = env.client.get("/api/state").json()["recent"]
    assert recent[-1]["record_id"] == a.id
    small = env.client.get(f"/api/results/{a.id}/thumb?width=160")  # no login: the operator screen shows it
    assert small.status_code == 200 and small.headers["content-type"] == "image/jpeg" and small.content[:2] == b"\xff\xd8"
    big = env.client.get(f"/api/results/{a.id}/thumb?width=64")
    assert big.status_code == 200 and cv2.imdecode(np.frombuffer(small.content, np.uint8), 1).shape[1] == 160
    assert cv2.imdecode(np.frombuffer(big.content, np.uint8), 1).shape[1] == 64
    assert env.client.get(f"/api/results/{a.id}/thumb?width=8").status_code == 422
    assert env.client.get("/api/results/nope/thumb").status_code == 404


def test_browse_filter_download_and_export_results(env):
    sup = login(env)
    store = env.results
    a = store.record(res(Outcome.FAIL, "Tampa ausente"), frame(), overlay=frame(10), **JOB)
    store.record(res(), frame(), **JOB)
    body = env.client.get("/api/results?outcome=FAIL", headers=sup).json()
    assert body["total"] == 1 and body["results"][0]["id"] == a.id and body["results"][0]["reason"] == "Tampa ausente"
    assert env.client.get("/api/results?limit=1", headers=sup).json()["total"] == 2
    assert env.client.get("/api/results?outcome=BAD", headers=sup).status_code == 422
    assert env.client.get(f"/api/results/{a.id}", headers=sup).json()["job_name"] == "Tampa azul"
    assert env.client.get("/api/results/nope", headers=sup).status_code == 404
    image = env.client.get(f"/api/results/{a.id}/image", headers=sup)
    assert image.headers["content-type"] == "image/jpeg" and image.content[:2] == b"\xff\xd8"
    assert env.client.get(f"/api/results/{a.id}/image?overlay=true", headers=sup).status_code == 200
    csv = env.client.get("/api/results.csv?outcome=FAIL", headers=sup)
    assert csv.status_code == 200 and csv.content.startswith(b"\xef\xbb\xbf") and "Tampa ausente" in csv.content.decode("utf-8-sig")
    assert env.client.get("/api/results").status_code == 401


def test_a_result_without_a_kept_image_has_no_image_endpoint(env):
    sup = login(env)
    r = env.results.record(res(Outcome.ERROR, "Câmera desconectada"), None, **JOB)
    assert env.client.get(f"/api/results/{r.id}/image", headers=sup).status_code == 404


# --- maintainer ----------------------------------------------------------------


def test_collection_mode_and_station_commands(env):
    mnt = login(env, "maintainer")
    r = env.client.post(f"/api/collection/{JOB['job_id']}", json={"enabled": True}, headers=mnt).json()
    assert r["enabled"] is True and env.results.collecting(JOB["job_id"])
    assert env.client.post("/api/station/pause", headers=mnt).json() == {"sent": "pause"}
    env.rig.tick(2)
    assert env.rig.state is State.PAUSED
    assert env.client.post("/api/station/resume", headers=mnt).status_code == 200
    env.rig.tick(5)
    assert env.rig.state is State.READY
    assert env.client.post("/api/station/explode", headers=mnt).status_code == 404


# --- the screens -----------------------------------------------------------------


def test_the_content_policy_allows_scripts_only_from_this_server(env):
    csp = env.client.get("/api/state").headers["content-security-policy"]
    assert "script-src 'self';" in csp and "unsafe-eval" not in csp and "unsafe-inline'; style" not in csp.split("script-src")[1][:30]
    assert "default-src 'self'" in csp and "frame-ancestors 'none'" in csp
    assert "[::1]" not in csp  # an IPv6 source in connect-src is invalid CSP syntax and the browser reports it as an error


def test_without_a_build_the_page_says_how_to_build_it_and_the_api_works(env):
    page = env.client.get("/")
    assert page.status_code == 503 and "npm run build" in page.text and "A interface não foi compilada" in page.text
    assert env.client.get("/jobs/abc").status_code == 503
    assert env.client.get("/api/state").status_code == 200


# --- the contract ----------------------------------------------------------------


def test_every_error_has_a_portuguese_message_and_a_machine_code(env):
    r = env.client.get("/api/jobs")
    assert r.status_code == 401 and r.json()["code"] == "login_required" and "Supervisor" in r.json()["detail"]
    sup = login(env)
    assert env.client.post("/api/station/pause", headers=sup).json()["code"] == "forbidden"
    assert env.client.get("/api/results/nope", headers=sup).json() == {"detail": "Esse resultado não existe", "code": "result_not_found"}
    assert env.client.get("/api/does-not-exist").json()["code"] == "not_found"
    bad = env.client.post("/api/login", json={"role": "supervisor"})
    assert bad.status_code == 422 and bad.json()["code"] == "validation_error" and "password" in bad.json()["fields"]
    for _ in range(5):
        env.client.post("/api/login", json={"role": "supervisor", "password": "wrong"})
    locked = env.client.post("/api/login", json={"role": "supervisor", "password": "x"})
    assert locked.status_code == 429 and locked.json()["code"] == "locked" and int(locked.headers["Retry-After"]) >= 1


def test_the_openapi_document_describes_every_path_and_the_live_messages(env):
    doc = env.client.get("/api/openapi.json").json()
    paths = doc["paths"]
    for path in ["/api/state", "/api/trigger", "/api/login", "/api/jobs", "/api/results", "/api/jobs/import", "/api/backup"]:
        assert path in paths, path
    assert all(p.startswith("/api/") for p in paths)  # nothing outside the prefix
    state = doc["paths"]["/api/state"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    assert state["$ref"].endswith("/StateOut")
    schemas = doc["components"]["schemas"]
    assert {"StateOut", "ResultOut", "RecordOut", "Problem", "LiveMessage", "StatusMessage", "StateMessage", "ResultMessage"} <= set(schemas)
    assert schemas["LiveMessage"]["discriminator"]["propertyName"] == "type"
    # every REST path says what it returns, so the generated client is typed
    untyped = [
        f"{method.upper()} {path}"
        for path, item in paths.items()
        for method, op in item.items()
        if "content" not in op["responses"].get("200", op["responses"].get("202", {"content": 1})) and "image" not in str(op["responses"])
    ]
    assert not untyped, untyped


def test_what_the_socket_sends_matches_the_documented_messages(env):
    from vision_station.api.schemas import LiveMessage
    from pydantic import TypeAdapter

    adapter = TypeAdapter(LiveMessage)
    with env.client.websocket_connect("/api/live") as ws:
        assert adapter.validate_python(ws.receive_json()).type == "status"
        env.rig.camera.scene = scene_with_object(40)
        seen = set()
        for _ in range(60):
            env.rig.tick(1)
            message = ws.receive()
            if message.get("text"):
                seen.add(adapter.validate_python(json.loads(message["text"])).type)
            if {"state", "result"} <= seen:
                break
        assert {"state", "result"} <= seen


# --- the built interface -----------------------------------------------------------


def built_dist(tmp_path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text('<!doctype html><html><body><div id="root"></div><script type="module" src="/assets/app-abc123.js"></script></body></html>', encoding="utf-8")
    (dist / "assets" / "app-abc123.js").write_text("console.log('app')", encoding="utf-8")
    (dist / "favicon.svg").write_text("<svg/>", encoding="utf-8")
    return dist


def test_the_built_interface_is_served_with_a_fallback_for_client_routes(env, tmp_path):
    env.deps.web_dist = built_dist(tmp_path)
    client = TestClient(create_app(env.deps))
    root = client.get("/")
    assert root.status_code == 200 and "app-abc123.js" in root.text and root.headers["cache-control"] == "no-cache"
    for deep in ["/jobs", "/jobs/abc/edit", "/results/xyz"]:  # a reload or a link on a client route still gets the app
        r = client.get(deep)
        assert r.status_code == 200 and "app-abc123.js" in r.text, deep
    asset = client.get("/assets/app-abc123.js")
    assert asset.status_code == 200 and asset.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert client.get("/favicon.svg").text == "<svg/>"
    assert client.get("/api/does-not-exist").json()["code"] == "not_found"  # the fallback never swallows the API
    assert client.get("/%2e%2e/%2e%2e/pyproject.toml").text.startswith("<!doctype")  # outside dist: the app, not the file
    csp = root.headers["content-security-policy"]
    assert "script-src 'self';" in csp and "sha256" not in csp  # a built page has no inline script


@pytest.mark.skipif(not (Path(__file__).parent.parent / "frontend/dist/index.html").is_file(), reason="the interface is not built (cd frontend && npm run build)")
def test_the_real_build_is_served_by_the_api(env):
    from vision_station.api.app import default_web_dist

    env.deps.web_dist = default_web_dist()
    client = TestClient(create_app(env.deps))
    html = client.get("/").text
    assets = re.findall(r'(?:src|href)="(/assets/[^"]+)"', html)
    assert any(a.endswith(".js") for a in assets) and any(a.endswith(".css") for a in assets)
    for url in assets:
        assert client.get(url).status_code == 200, url
    assert 'id="root"' in client.get("/jobs/anything").text  # a client route
    assert client.get("/api/state").json()["state"] == "Ready"


def test_recent_results_are_the_last_ten_oldest_first_and_every_result_says_when(env):
    for i in range(12):
        env.results.record(res(Outcome.FAIL if i % 2 else Outcome.PASS, f"r{i}"), frame(), **JOB)
    recent = env.client.get("/api/state").json()["recent"]
    assert [r["reason"] for r in recent] == [f"r{i}" for i in range(2, 12)]
    assert all(r["at"].startswith("2026-") or r["at"][:2] == "20" for r in recent)


def test_about_is_for_supervisors_and_lists_the_tools_this_software_can_run(env):
    assert env.client.get("/api/about").status_code == 401
    body = env.client.get("/api/about", headers=login(env)).json()
    assert body["job_format"] == 1 and body["version"]
    assert {"name": "code", "version": 1} in body["tools"]


def test_the_built_interface_is_looked_for_in_frontend_dist_unless_told_otherwise(monkeypatch, tmp_path):
    from vision_station.api.app import default_web_dist

    monkeypatch.delenv("VISION_STATION_WEB", raising=False)
    assert default_web_dist() == Path(__file__).parent.parent / "frontend" / "dist"
    monkeypatch.setenv("VISION_STATION_WEB", str(tmp_path))
    assert default_web_dist() == tmp_path


def test_a_verdict_held_after_the_station_armed_again_shows_in_the_state_and_the_socket(env):
    """VIA-0049: the station is Ready (the next request is accepted), but the verdict is still to be shown."""
    published = []
    env.deps.hub.publish = published.append
    request = env.client.post("/api/inspections", json={"reference": "peça-1"})
    assert request.status_code == 202
    env.rig.tick(8)  # nothing in front of the camera: inspected, then armed again at once
    body = env.client.get("/api/state").json()
    assert body["state"] == "Ready" and body["showing_result"] is True and body["message"] == "PASS"
    assert env.client.post("/api/inspections", json={}).status_code == 202  # not holding the station
    env.rig.tick(30)
    body = env.client.get("/api/state").json()
    assert body["showing_result"] is False and body["message"] == "Aguardando objeto"
    states = [m for m in published if m["type"] == "state"]
    assert states and all("showing_result" in m for m in states) and states[-1]["showing_result"] is False


def test_two_requests_at_once_are_one_inspection_and_a_409_never_two_accepted(env):
    """VIA-0051: both requests saw Ready before the station took the first; both got 202, one inspection
    ran, and the other request expired after 30 s."""
    first = env.client.post("/api/inspections", json={"reference": "a"})
    second = env.client.post("/api/inspections", json={"reference": "b"})
    assert first.status_code == 202
    assert second.status_code == 409 and second.json()["code"] == "station_not_ready"
    assert env.client.post("/api/trigger").status_code == 409  # the button too
    env.rig.tick(8)
    done = env.client.get(f"/api/inspections/{first.json()['id']}").json()
    assert done["status"] == "done" and done["reference"] == "a"
    assert env.client.post("/api/inspections", json={"reference": "c"}).status_code == 202  # free again


def test_the_reason_code_filter_and_the_dataset_grid_are_served_with_their_roles(env):
    sup, mnt = login(env), login(env, "maintainer")
    assert env.client.get("/api/results/reason-codes").status_code == 401
    assert env.client.get("/api/results/reason-codes", headers=sup).json() == {"codes": []}
    assert env.client.get("/api/results?reason_code=color.min_fraction", headers=sup).json()["total"] == 0
    assert env.client.get("/api/results.csv?reason_code=color.min_fraction", headers=sup).status_code == 200
    job = JOB["job_id"]
    assert env.client.get(f"/api/dataset/{job}/images", headers=sup).status_code == 403  # the dataset is the Maintainer's
    assert env.client.get(f"/api/dataset/{job}/images", headers=mnt).json() == {"total": 0, "images": []}
    assert env.client.get(f"/api/dataset/{job}/images/nothing.jpg", headers=mnt).status_code == 404


def test_a_dataset_image_is_served_reduced_for_the_grid(env):
    mnt = login(env, "maintainer")
    job = JOB["job_id"]
    env.results.set_collection(job, True)
    env.results.record(res(Outcome.PASS), np.zeros((1080, 1920, 3), np.uint8), **JOB)
    listing = env.client.get(f"/api/dataset/{job}/images", headers=mnt).json()
    assert listing["total"] == 1 and listing["images"][0]["source"] == "collected" and listing["images"][0]["label"] is None
    image_id = listing["images"][0]["id"]
    small = env.client.get(f"/api/dataset/{job}/images/{image_id}.jpg?width=320", headers=mnt)
    assert small.status_code == 200 and small.headers["content-type"] == "image/jpeg"
    shown = cv2.imdecode(np.frombuffer(small.content, np.uint8), cv2.IMREAD_COLOR)
    assert shown.shape[1] == 320 and shown.shape[0] == 180  # reduced, same proportion
    assert env.client.get(f"/api/dataset/other-job/images/{image_id}.jpg", headers=mnt).status_code == 404
