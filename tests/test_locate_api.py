"""The anchor step's own run: the locating step of a draft on its reference picture and every sample (frontend.md §7.3)."""

import base64

import cv2
import numpy as np
import yaml

from test_api import env, login  # noqa: F401
from test_fixtures_pipeline import BENCH, job, part_scene
from test_manage_api import mnt  # noqa: F401
from vision_station.verification import make_reference_files
from vision_station.verification.reference import EXPECTED_FILE


def png(image) -> str:
    return base64.b64encode(cv2.imencode(".png", image)[1].tobytes()).decode()


def draft_with_samples(range_=None):
    bundle = job()
    data = bundle.job.model_dump(mode="json")
    if range_:
        data["geometry"]["fixtures"][0]["range"] = range_
    files = {
        **{p: base64.b64encode(d).decode() for p, d in make_reference_files(part_scene()).items()},
        "tests/images/a-straight.png": png(part_scene()),
        "tests/images/b-turned.png": png(part_scene(12.0)),
        "tests/images/c-too-turned.png": png(part_scene(28.0)),
        "tests/images/d-empty.png": png(np.full((480, 640, 3), BENCH, np.uint8)),
        EXPECTED_FILE: base64.b64encode(yaml.safe_dump({"cases": [
            {"image": "tests/images/a-straight.png", "outcome": "PASS"},
            {"image": "tests/images/b-turned.png", "outcome": "PASS"},
            {"image": "tests/images/c-too-turned.png", "outcome": "FAIL"},
            {"image": "tests/images/d-empty.png", "outcome": "FAIL"},
        ]}).encode()).decode(),
    }
    return {"job": data, "profile": bundle.profile.model_dump(mode="json"), "add_files": files, "notes": ""}


def test_the_pose_is_given_on_the_reference_and_on_each_sample_and_why_when_there_is_none(env, mnt):  # noqa: F811
    out = env.client.post("/api/editor/locate", headers=mnt, json=draft_with_samples()).json()
    assert out["ok"] is True
    by = {s["image"].split("/")[-1]: s for s in out["samples"]}
    assert list(by)[0] == "reference.png" and by["reference.png"]["kind"] == "reference"
    ref = by["reference.png"]["fixtures"][0]
    assert by["reference.png"]["found"] and abs(ref["angle"]) < 1.5 and ref["taught"] and ref["name"] == "anchor"
    assert by["a-straight.png"]["found"] and by["a-straight.png"]["kind"] == "good"
    turned = by["b-turned.png"]
    assert turned["found"] and abs(turned["fixtures"][0]["angle"] - 12.0) < 1.5 and len(turned["fixtures"][0]["corners"]) == 4
    # beyond the range of the job: found, but not accepted, with the code and the reason
    far = by["c-too-turned.png"]
    assert far["found"] is False and far["error_code"] == 202 and "girado" in far["reason"] and far["kind"] == "bad"
    assert [round(f["angle"]) for f in far["fixtures"]] == [28]  # what was found is shown, so the person sees how far off it is
    # nothing to find
    empty = by["d-empty.png"]
    assert empty["found"] is False and empty["error_code"] == 201 and empty["fixtures"] == []


def test_the_range_of_the_draft_decides_and_the_answer_follows_the_language(env, mnt):  # noqa: F811
    wide = draft_with_samples({"angle": [-40, 40], "scale": [0.9, 1.1]})
    by = {s["image"].split("/")[-1]: s for s in env.client.post("/api/editor/locate", headers=mnt, json=wide).json()["samples"]}
    assert by["c-too-turned.png"]["found"] is True
    english = env.client.post("/api/editor/locate", headers={**mnt, "Accept-Language": "en"}, json=draft_with_samples()).json()
    far = next(s for s in english["samples"] if s["image"].endswith("c-too-turned.png"))
    assert far["reason"].startswith("Object 'anchor' is turned")


def test_a_refused_draft_and_the_roles_are_answered(env, mnt):  # noqa: F811
    bad = draft_with_samples()
    bad["job"]["tools"][0]["roi"] = "nowhere"
    out = env.client.post("/api/editor/locate", headers=mnt, json=bad).json()
    assert out["ok"] is False and out["samples"] == [] and out["message"]
    assert env.client.post("/api/editor/locate", json=draft_with_samples()).status_code == 401
    assert env.client.post("/api/editor/locate", headers=login(env), json=draft_with_samples()).status_code == 403  # the editor's, not the fine-tune's
