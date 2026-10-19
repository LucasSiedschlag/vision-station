"""The fine-tune of tolerances by the Supervisor (FR-JOB-14, UC-15, document 05 §7.12): the server decides what may change."""

import io
import zipfile

import yaml

from test_api import env, login  # noqa: F401
from test_manage_api import b64, create, mnt  # noqa: F401
from test_verification import no_code_scene, png, qr_scene
from vision_station.store import JobRef
from vision_station.verification.reference import EXPECTED_FILE


def start(env, mnt):  # noqa: F811
    """The version a fine-tune starts from, as the screen builds its draft: read with the supervisor's own login."""
    sup = login(env)
    job_id = create(env, mnt)
    v = env.client.get(f"/api/jobs/{job_id}/versions/1", headers=sup)
    assert v.status_code == 200, v.text
    body = v.json()
    draft = {"job": body["job"], "profile": body["profile"], "base": {"id": job_id, "version": 1}, "latest": 1, "add_files": {}, "remove_files": [], "notes": "a luz mudou"}
    return sup, job_id, draft


def tune(env, sup, job_id, draft):  # noqa: F811
    return env.client.post(f"/api/jobs/{job_id}/tune", headers=sup, json=draft)


def test_a_supervisor_saves_a_limit_as_the_next_version_which_is_verified_and_not_active(env, mnt):  # noqa: F811
    sup, job_id, draft = start(env, mnt)
    draft["job"]["tools"][0]["params"] = {"min_count": 2}  # the limit moves: a tunable parameter
    r = tune(env, sup, job_id, draft)
    assert r.status_code == 201, r.text
    out = r.json()
    assert out["version"] == 2 and out["changes"] == ["lote: min_count, None → 2"]
    assert out["verified"] is False and out["problems"]  # no sample has two codes: the job no longer passes its own good ones
    detail = env.client.get(f"/api/jobs/{job_id}", headers=sup).json()
    two = next(v for v in detail["versions"] if v["version"] == 2)
    assert two["tuned"] is True and two["parent_version"] == 1 and two["active"] is False and two["author"] == "supervisor"
    assert next(v for v in detail["versions"] if v["version"] == 1)["tuned"] is False
    event = [e for e in env.client.get("/api/audit", headers=sup).json()["events"] if e["kind"] == "job_tune"][0]
    assert event["data"]["notes"] == "a luz mudou" and event["data"]["changes"] == [{"tool": "lote", "param": "min_count", "old": None, "new": 2}]


def test_a_tuned_version_that_still_passes_its_samples_is_verified(env, mnt):  # noqa: F811
    sup, job_id, draft = start(env, mnt)
    draft["job"]["tools"][0]["params"] = {"max_count": 3}  # looser: the good samples still pass, the blank one still fails
    out = tune(env, sup, job_id, draft).json()
    assert out["verified"] is True and out["problems"] == []


def test_anything_but_a_limit_is_refused_with_where(env, mnt):  # noqa: F811
    sup, job_id, draft = start(env, mnt)
    cases = {
        "tools.0.params.expect": lambda d: d["job"]["tools"][0].update(params={"expect": "OUTRO"}),  # what is measured
        "tools.0.roi": lambda d: d["job"]["tools"][0].update(roi="frame"),
        "geometry.rois.label.rect": lambda d: d["job"]["geometry"]["rois"]["label"].update(rect=[0, 0, 0.5, 0.5]),
        "quality.sharpness_min_ratio": lambda d: d["job"]["quality"].update(sharpness_min_ratio=0.1),
        "tools.0.reason_fail": lambda d: d["job"]["tools"][0].update(reason_fail="outro"),
        "trigger.mode": lambda d: d["job"]["trigger"].update(mode="manual"),
        "profile": lambda d: d["profile"].update(power_line_hz=50),
        "tools": lambda d: d["job"]["tools"].append({**d["job"]["tools"][0], "id": "outra"}),
    }
    for path, change in cases.items():
        _, _, bad = start(env, mnt)  # a job of its own each time: a refused save leaves nothing behind
        change(bad)
        r = tune(env, sup, bad["base"]["id"], bad)
        assert r.status_code == 422, (path, r.text)
        body = r.json()
        assert body["code"] == "not_tunable" and any(f.startswith(path) or path.startswith(f) for f in body["fields"]), (path, body)
        assert env.jobs.versions(bad["base"]["id"]) == [1]


def test_a_note_is_required_and_a_stale_draft_is_refused(env, mnt):  # noqa: F811
    sup, job_id, draft = start(env, mnt)
    draft["job"]["tools"][0]["params"] = {"max_count": 3}
    assert tune(env, sup, job_id, {**draft, "notes": "  "}).status_code == 422
    assert tune(env, sup, job_id, draft).status_code == 201
    stale = tune(env, sup, job_id, draft)  # the same draft again: version 2 exists now
    assert stale.status_code == 409 and stale.json()["code"] == "stale_draft"


def test_samples_may_be_added_but_the_ones_the_job_has_are_never_changed_or_taken_out(env, mnt):  # noqa: F811
    sup, job_id, draft = start(env, mnt)
    base = env.jobs.load(JobRef(job_id, 1))
    expected = yaml.safe_load(base.extra[EXPECTED_FILE])
    new = {"image": "tests/images/boa3.png", "outcome": "PASS"}
    ok = {**draft, "add_files": {"tests/images/boa3.png": b64(png(qr_scene("LOTE-3"))), EXPECTED_FILE: b64(yaml.safe_dump({**expected, "cases": [*expected["cases"], new]}).encode())}}
    assert tune(env, sup, job_id, ok).status_code == 201
    # a sample that is already there changes: refused
    sup, job_id, draft = start(env, mnt)
    changed = {**draft, "add_files": {"tests/images/ok1.png": b64(png(no_code_scene()))}}
    r = tune(env, sup, job_id, changed)
    assert r.status_code == 422 and "files.tests/images/ok1.png" in r.json()["fields"]
    # a case of the reference set taken out, or turned around: refused
    cases = [dict(c) for c in expected["cases"]]
    cases[0]["outcome"] = "FAIL"
    turned = {**draft, "add_files": {EXPECTED_FILE: b64(yaml.safe_dump({**expected, "cases": cases}).encode())}}
    assert tune(env, sup, job_id, turned).status_code == 422
    # a file outside the samples
    other = {**draft, "add_files": {"models/x.onnx": b64(b"x")}}
    assert tune(env, sup, job_id, other).status_code == 422


def test_the_role_decides_who_may_tune_and_a_normal_version_does_not_carry_the_mark(env, mnt):  # noqa: F811
    sup, job_id, draft = start(env, mnt)
    draft["job"]["tools"][0]["params"] = {"max_count": 3}
    assert env.client.post(f"/api/jobs/{job_id}/tune", json=draft).status_code == 401
    assert tune(env, mnt, job_id, draft).status_code == 201  # the Maintainer may too
    files = env.jobs.export_vjob(JobRef(job_id, 1))
    assert b"tuned" not in zipfile.ZipFile(io.BytesIO(files)).read("job.yaml")  # written only when true: older programs still read it
