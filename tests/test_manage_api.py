"""Management endpoints (VIA-0026): types, jobs as drafts, camera tuning, reference, users, audit, dataset."""

import base64
import time

import cv2
import numpy as np
import pytest

from test_api import env, login  # noqa: F401  (the fixture)
from test_verification import make_bundle, no_code_scene, png, qr_scene
from vision_station.pipeline import draw_overlay, inspect_job


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


def draft(name="Etiqueta de lote", **changes):
    bundle = make_bundle()
    job = bundle.job.model_dump(mode="json")
    job["job"]["name"] = name
    job.update(changes)
    return {"job": job, "profile": bundle.profile.model_dump(mode="json"), "add_files": {p: b64(d) for p, d in bundle.extra.items()}, "notes": "primeira"}


@pytest.fixture
def mnt(env):
    env.deps.inspect = inspect_job
    env.deps.overlay = draw_overlay
    return login(env, "maintainer")


def create(env, mnt, **kw):
    r = env.client.post("/api/jobs", headers=mnt, json=draft(**kw))
    assert r.status_code == 201, r.text
    return r.json()["id"]


# --- types ---------------------------------------------------------------------------------------------


def test_types_with_their_parameter_schemas(env, mnt):
    assert env.client.get("/api/tools").status_code == 401
    assert env.client.get("/api/tools", headers=login(env)).status_code == 200  # the fine-tune draws its gauges from the criteria (FR-JOB-14)
    body = env.client.get("/api/tools", headers=mnt).json()
    tools = {t["name"]: t for t in body["tools"]}
    assert {"code", "color", "pattern"} <= set(tools)
    assert "min_fraction" in tools["color"]["params_schema"]["properties"]
    assert {"fixed", "template", "blob"} <= {t["name"] for t in body["locators"]}
    for kind in body["tools"] + body["locators"]:  # shown in the editor: Portuguese, never the code's docstring (VIA-0048)
        assert kind["description"] and kind["description"] == kind["params_schema"].get("description"), kind["name"]
        assert " tool" not in kind["description"] and "Locator" not in kind["description"], kind["description"]
    assert body["builtin_rois"] == ["anchor", "frame"]


def test_verify_runs_the_draft_on_every_sample_like_activation_does(env, mnt):
    body = env.client.post("/api/jobs/verify", headers=mnt, json=draft()).json()
    assert body["ok"] is True and body["message"] is None
    assert [c["image"] for c in body["cases"]] == ["tests/images/ok1.png", "tests/images/ok2.png", "tests/images/blank.png"]
    assert [(c["expected"], c["outcome"], c["ok"]) for c in body["cases"]] == [("PASS", "PASS", True), ("PASS", "PASS", True), ("FAIL", "FAIL", True)]
    assert body["cases"][2]["reason"] == "Código não lido" and body["max_ms"] >= 0
    # a sample that the job judges differently is a failed case, with the words that say why
    bad = draft()
    bad["job"]["tools"][0]["params"] = {"expect": "OUTRO"}
    failed = env.client.post("/api/jobs/verify", headers=mnt, json=bad).json()
    assert failed["ok"] is False
    assert not failed["cases"][0]["ok"] and "esperado PASS" in failed["cases"][0]["message"]
    english = env.client.post("/api/jobs/verify", headers={**mnt, "Accept-Language": "en"}, json=bad).json()
    assert "expected PASS" in english["cases"][0]["message"]


def test_verify_says_so_when_there_is_nothing_to_run_or_the_draft_is_refused(env, mnt):
    none = draft()
    none["add_files"] = {p: d for p, d in none["add_files"].items() if not p.startswith("tests/")}
    body = env.client.post("/api/jobs/verify", headers=mnt, json=none).json()
    assert body["ok"] is False and body["cases"] == [] and "amostras" in body["message"]
    refused = draft()
    refused["job"]["tools"][0]["roi"] = "nowhere"
    out = env.client.post("/api/jobs/verify", headers=mnt, json=refused).json()
    assert out["ok"] is False and out["cases"] == []
    assert env.client.post("/api/jobs/verify", json=draft()).status_code == 401


# --- jobs ----------------------------------------------------------------------------------------------


def test_create_read_and_open_a_job(env, mnt):
    job_id = create(env, mnt)
    detail = env.client.get(f"/api/jobs/{job_id}", headers=login(env)).json()
    assert detail["name"] == "Etiqueta de lote" and len(detail["versions"]) == 1
    v1 = detail["versions"][0]
    assert v1["version"] == 1 and v1["author"] == "maintainer" and v1["notes"] == "primeira" and not v1["active"]
    full = env.client.get(f"/api/jobs/{job_id}/versions/1", headers=mnt).json()
    assert full["job"]["tools"][0]["type"] == "code" and full["profile"]
    assert {"reference/reference.png", "tests/expected.yaml"} <= {f["path"] for f in full["files"]}
    assert full["reference"]["sharpness"] > 0 and len(full["expected"]["cases"]) == 3
    img = env.client.get(f"/api/jobs/{job_id}/versions/1/files/reference/reference.png", headers=mnt)
    assert img.status_code == 200 and img.headers["content-type"] == "image/png"
    assert env.client.get(f"/api/jobs/{job_id}/versions/9", headers=mnt).status_code == 404
    assert any(a["kind"] == "job_create" and a["job_id"] == job_id for a in env.jobs.read_audit())


def test_validate_reports_fields_and_jobs_that_cannot_run(env, mnt):
    assert env.client.post("/api/jobs/validate", headers=mnt, json=draft()).json() == {"ok": True, "message": None, "fields": {}}
    bad = draft()
    del bad["job"]["quality"]["brightness"]
    body = env.client.post("/api/jobs/validate", headers=mnt, json=bad).json()
    assert not body["ok"] and "job.quality.brightness" in body["fields"]
    wrong = draft()
    wrong["job"]["tools"][0]["params"] = {"formats": ["NoSuchCode"]}
    body = env.client.post("/api/jobs/validate", headers=mnt, json=wrong).json()
    assert not body["ok"] and "não pode rodar" in body["message"] and not body["fields"]
    needs_file = draft()
    needs_file["job"]["tools"].append({"id": "marca", "type": "pattern", "version": 1, "roi": "label", "params": {"template": "patterns/x.png"}, "reason_fail": "x"})
    assert "patterns/x.png" in env.client.post("/api/jobs/validate", headers=mnt, json=needs_file).json()["message"]
    assert env.client.post("/api/jobs", headers=mnt, json=bad).status_code == 422


def test_a_draft_from_an_older_version_saves_when_it_saw_the_latest(env, mnt):
    """VIA-0047: the editor opens any version; `base` is where the files come from, `latest` what it saw last."""
    job_id = create(env, mnt)
    v2 = draft(name="Segunda")
    v2.update(add_files={}, base={"id": job_id, "version": 1})
    assert env.client.post(f"/api/jobs/{job_id}/versions", headers=mnt, json=v2).json()["version"] == 2
    from_v1 = draft(name="De volta à primeira")
    from_v1.update(add_files={}, base={"id": job_id, "version": 1}, latest=2, notes="a partir da v1")
    r = env.client.post(f"/api/jobs/{job_id}/versions", headers=mnt, json=from_v1)
    assert r.status_code == 201 and r.json()["version"] == 3
    v3 = env.client.get(f"/api/jobs/{job_id}/versions/3", headers=mnt).json()
    assert v3["job"]["job"]["parent_version"] == 2 and "reference/reference.png" in {f["path"] for f in v3["files"]}
    stale = env.client.post(f"/api/jobs/{job_id}/versions", headers=mnt, json=from_v1)  # saw v2, the latest is now v3
    assert stale.status_code == 409 and stale.json()["code"] == "stale_draft" and stale.json()["latest"] == 3


def test_a_new_version_builds_on_the_latest_and_keeps_its_files(env, mnt):
    job_id = create(env, mnt)
    edit = draft(name="Etiqueta de lote (nova luz)")
    edit.update(add_files={}, base={"id": job_id, "version": 1}, notes="luz nova")
    r = env.client.post(f"/api/jobs/{job_id}/versions", headers=mnt, json=edit)
    assert r.status_code == 201 and r.json() == {"id": job_id, "version": 2}
    v2 = env.client.get(f"/api/jobs/{job_id}/versions/2", headers=mnt).json()
    assert v2["job"]["job"]["parent_version"] == 1 and "reference/reference.png" in {f["path"] for f in v2["files"]}
    stale = env.client.post(f"/api/jobs/{job_id}/versions", headers=mnt, json=edit)  # still based on v1
    assert stale.status_code == 409 and stale.json()["code"] == "stale_draft" and stale.json()["latest"] == 2
    edit.update(base={"id": job_id, "version": 2}, remove_files=["tests/images/ok2.png"])
    assert env.client.post(f"/api/jobs/{job_id}/versions", headers=mnt, json=edit).status_code == 422  # expected.yaml still names it
    diff = env.client.get(f"/api/jobs/{job_id}/versions/2/diff?against=1", headers=login(env)).json()["diff"]
    assert "-  name: Etiqueta de lote\n" in diff and "+  name: Etiqueta de lote (nova luz)\n" in diff


def test_duplicate(env, mnt):
    job_id = create(env, mnt)
    r = env.client.post(f"/api/jobs/{job_id}/duplicate", headers=mnt, json={"version": 1, "name": "Cópia"})
    assert r.status_code == 201
    new = r.json()["id"]
    assert new != job_id and env.client.get(f"/api/jobs/{new}", headers=mnt).json()["name"] == "Cópia"
    assert len(env.client.get(f"/api/jobs/{new}/versions/1", headers=mnt).json()["files"]) == len(make_bundle().extra)


def test_run_a_draft_on_an_image_or_the_live_frame(env, mnt):
    body = env.client.post("/api/jobs/test", headers=mnt, json={"draft": draft(), "image": b64(png(qr_scene("LOTE-9")))}).json()
    assert body["result"]["outcome"] == "PASS" and body["regions"][0]["passed"] and (body["width"], body["height"]) == (320, 240)
    assert body["tools"]["lote"]["codes"][0]["text"] == "LOTE-9" and "total" in body["timings"]
    overlay = cv2.imdecode(np.frombuffer(base64.b64decode(body["overlay"]), np.uint8), cv2.IMREAD_COLOR)
    assert overlay.shape == (240, 320, 3)
    fail = env.client.post("/api/jobs/test", headers=mnt, json={"draft": draft(), "image": b64(png(no_code_scene()))}).json()
    assert fail["result"]["outcome"] == "FAIL" and not fail["regions"][0]["passed"]
    live = env.client.post("/api/jobs/test", headers=mnt, json={"draft": draft()})
    assert live.status_code == 200 and live.json()["result"]["outcome"] in ("FAIL", "ERROR")  # the rig shows a plain scene
    bad = env.client.post("/api/jobs/test", headers=mnt, json={"draft": draft(), "image": b64(b"not an image")})
    assert bad.status_code == 400 and bad.json()["code"] == "bad_image"


# --- camera, reference ----------------------------------------------------------------------------------


def test_camera_tuning_pauses_the_station_and_reports_each_setting(env, mnt):
    state = env.client.get("/api/camera/state", headers=mnt).json()
    assert state["connected"] and state["profile"] and not state["station_paused"]
    profile = dict(state["profile"], exposure={"mode": "manual", "value_us": 12000})
    r = env.client.post("/api/camera/apply?wait_s=0", headers=mnt, json=profile)
    assert r.status_code == 200
    env.rig.tick(2)
    after = env.client.get("/api/camera/state", headers=mnt).json()
    assert after["station_paused"] and after["applied"] and after["profile"]["exposure"]["value_us"] == 12000 and after["settings"]
    assert env.client.post("/api/camera/apply", headers=mnt, json={"exposure": "bright"}).status_code == 422
    env.client.post("/api/station/resume", headers=mnt)
    env.rig.tick(5)
    assert env.client.get("/api/camera/state", headers=mnt).json()["profile"]["exposure"]["value_us"] != 12000  # the job's again


def test_auto_exposure_measures_once_pauses_the_station_and_leaves_the_camera_on_the_result(env, mnt, monkeypatch):
    from types import SimpleNamespace

    from vision_station.station import exposure

    # the acquisition thread does not run in these tests: waiting for the camera runs the rig by hand
    monkeypatch.setattr(exposure, "time", SimpleNamespace(sleep=lambda s: env.rig.tick(1), monotonic=time.monotonic))
    profile = env.client.get("/api/camera/state", headers=mnt).json()["profile"]
    profile["exposure"] = {"mode": "manual", "value_us": 8000, "auto_once": {"target_brightness": 5, "max_exposure_us": 50000}}
    r = env.client.post("/api/camera/auto-exposure", headers=mnt, json=profile)
    assert r.status_code == 200, r.text
    found = r.json()
    assert found["limit"] == "max" and found["value_us"] == 50000 and not found["reached"]  # the scene never saturates
    assert found["target_percent"] == 5 and found["steps"][0] == {"exposure_us": 50000.0, "saturated_percent": 0.0}
    state = env.client.get("/api/camera/state", headers=mnt).json()
    assert state["station_paused"] and state["profile"]["exposure"]["value_us"] == 50000 and state["profile"]["exposure"]["mode"] == "manual"
    assert env.client.post("/api/camera/auto-exposure", headers=mnt, json={"exposure": "bright"}).status_code == 422
    assert env.client.post("/api/camera/auto-exposure", json=profile).status_code == 401
    assert env.client.post("/api/camera/auto-exposure", headers=login(env), json=profile).status_code == 403


def test_auto_exposure_says_so_when_there_is_no_camera(env, mnt):
    env.rig.camera.fail_read = True
    env.rig.tick(3)  # the acquisition notices the loss
    profile = env.client.get("/api/camera/state", headers=mnt).json()["profile"]
    r = env.client.post("/api/camera/auto-exposure", headers=mnt, json=profile)
    assert r.status_code == 409 and r.json()["code"] == "camera_not_connected"


def test_reference_image_and_reference_cases(env, mnt):
    ref = env.client.post("/api/reference/capture", headers=mnt, json={"image": b64(png(qr_scene("A-1")))}).json()
    assert set(ref["files"]) == {"reference/reference.png", "reference/reference.meta.yaml"} and ref["sharpness"] > 0
    case = env.client.post("/api/reference/cases", headers=mnt, json={"draft": draft(), "image": b64(png(qr_scene("LOTE-3"))), "name": "ok3"}).json()
    assert case["path"] == "tests/images/ok3.png" and case["result"]["outcome"] == "PASS" and case["image"]
    assert env.client.post("/api/reference/cases", headers=mnt, json={"draft": draft(), "name": "../x"}).status_code == 422


# --- backups, users, audit, dataset -------------------------------------------------------------------


def test_backups_are_listed(env, mnt):
    create(env, mnt)
    sup = login(env)
    assert env.client.get("/api/backup", headers=sup).json()["backups"] == []
    name = env.client.post("/api/backup", headers=sup).json()["name"]
    listed = env.client.get("/api/backup", headers=sup).json()
    assert [b["name"] for b in listed["backups"]] == [name] and listed["backups"][0]["size"] > 0


def test_passwords_and_sessions(env, mnt):
    sup = login(env)
    users = env.client.get("/api/users", headers=sup).json()["users"]
    assert [u["role"] for u in users] == ["supervisor", "maintainer"] and all(u["has_password"] and u["changed_at"] for u in users)
    assert env.client.put("/api/users/maintainer/password", headers=sup, json={"password": "outra-senha-1"}).status_code == 403
    r = env.client.put("/api/users/supervisor/password", headers=sup, json={"password": "outra-senha-1", "current_password": "errada"})
    assert r.status_code == 400 and r.json()["code"] == "wrong_password"
    r = env.client.put("/api/users/supervisor/password", headers=sup, json={"password": "outra-senha-1", "current_password": "supervisor-pass"})
    assert r.status_code == 200 and r.json()["has_password"]
    assert env.client.get("/api/users", headers=sup).status_code == 401  # a new password ends the old sessions
    assert env.client.put("/api/users/supervisor/password", headers=mnt, json={"password": "curta"}).status_code == 422
    assert env.client.put("/api/users/supervisor/password", headers=mnt, json={"password": "supervisor-pass"}).status_code == 200
    assert env.client.post("/api/users/sessions/revoke", headers=mnt).json()["revoked"] >= 1
    assert env.client.get("/api/tools", headers=mnt).status_code == 401
    kinds = [a["kind"] for a in env.jobs.read_audit()]
    assert kinds.count("password_set") == 2 and "sessions_revoked" in kinds


def test_audit_filters_and_csv(env, mnt):
    job_id = create(env, mnt)
    create(env, mnt)
    sup = login(env)
    body = env.client.get("/api/audit?kind=job_create", headers=sup).json()
    assert body["total"] == 2 and body["events"][0]["kind"] == "job_create" and body["events"][0]["data"]["by"] == "maintainer"
    assert env.client.get(f"/api/audit?job_id={job_id}", headers=sup).json()["total"] == 1
    assert len(env.client.get("/api/audit?limit=1", headers=sup).json()["events"]) == 1
    csv = env.client.get("/api/audit.csv", headers=sup)
    assert csv.content.startswith(b"\xef\xbb\xbf") and "job_create" in csv.content.decode("utf-8-sig")


def test_dataset_counts_and_export(env, mnt):
    job_id = create(env, mnt)
    body = env.client.get("/api/dataset", headers=mnt).json()
    assert body["jobs"] == [{"job_id": job_id, "name": "Etiqueta de lote", "collecting": False, "images": 0}] and body["total"] == 0
    empty = env.client.post("/api/dataset/export", headers=mnt, json={})
    assert empty.status_code == 409 and empty.json()["code"] == "dataset_empty"
    record = env.results.record(*_one_result(env), job_id=job_id, job_name="Etiqueta de lote", job_version=1)
    env.results.mark_incorrect(record.id, "FAIL", by="supervisor")
    out = env.client.post("/api/dataset/export", headers=mnt, json={}).json()
    assert out["count"] == 1 and out["folder"].startswith(str(env.jobs.root / "exports"))


def _one_result(env):
    from vision_station.core.results import InspectionResult, Outcome

    return InspectionResult(Outcome.PASS), qr_scene("X")


def test_a_draft_result_is_simulated_with_its_tools_and_reason_codes(env, mnt):
    fail = env.client.post("/api/jobs/test", headers=mnt, json={"draft": draft(), "image": b64(png(no_code_scene()))}).json()["result"]
    assert fail["simulated"] is True and fail["sequence"] is None  # never a production result
    assert fail["reason_codes"] == [{"tool": "lote", "code": "code.min_count"}]
    (tool,) = fail["tools"]
    assert tool["units"]["matching"] == "count" and tool["criteria"][0]["code"] == "min_count" and tool["margin"] == -1
