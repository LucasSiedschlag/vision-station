"""The interface for other programs (FR-INT-1): trigger with an id, the result and its pictures, CORS."""

import threading
import time

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from test_api import env  # noqa: F401  (the fixture)
from test_station import scene_with_object
from vision_station.api import create_app
from vision_station.api.inspections import InspectionRegistry
from vision_station.pipeline import draw_overlay
from vision_station.records import RecordingConfig
from vision_station.core.results import Outcome


def run_until_done(env, id, ticks=60):
    for _ in range(ticks):
        env.rig.tick()
        body = env.client.get(f"/api/inspections/{id}").json()
        if body["status"] != "pending":
            return body
    raise AssertionError("the inspection never finished")


def test_a_requested_inspection_comes_back_with_its_reference_result_and_pictures(env):
    env.deps.overlay = draw_overlay
    r = env.client.post("/api/inspections", json={"reference": "caixa-17"})
    assert r.status_code == 202
    req = r.json()
    assert req["status"] == "pending" and req["reference"] == "caixa-17" and req["result"] is None
    body = run_until_done(env, req["id"])
    assert body["status"] == "done" and body["reference"] == "caixa-17"
    assert body["result"]["outcome"] == "PASS" and body["result"]["at"]
    assert body["job"]["name"] and body["record_id"] == env.recorder.last_record_id
    for url in (body["frame_url"], body["overlay_url"]):
        img = env.client.get(url)
        assert img.status_code == 200 and img.headers["content-type"] == "image/jpeg"
        assert cv2.imdecode(np.frombuffer(img.content, np.uint8), cv2.IMREAD_COLOR) is not None


def test_the_result_says_fail_with_the_reason(env):
    env.rig.outcome = Outcome.FAIL
    body = run_until_done(env, env.client.post("/api/inspections").json()["id"])
    assert body["result"]["outcome"] == "FAIL" and body["result"]["reason"] == "Tampa ausente"
    assert body["overlay_url"] is None  # no overlay drawer configured: only the frame


def test_not_ready_is_refused_with_the_state(env):
    env.client.post("/api/inspections")
    env.rig.tick()
    r = env.client.post("/api/inspections")  # inspecting or showing the result
    assert r.status_code == 409 and r.json()["code"] == "station_not_ready" and r.json()["state"]


def test_a_request_that_never_runs_expires_and_is_never_a_pass(env):
    env.deps.inspections = InspectionRegistry(expire_s=0.0)
    id = env.client.post("/api/inspections").json()["id"]
    time.sleep(0.01)
    body = env.client.get(f"/api/inspections/{id}").json()
    assert body["status"] == "expired" and body["result"] is None and body["message"].startswith("A inspeção não aconteceu")


def test_waiting_for_the_result(env):
    id = env.client.post("/api/inspections").json()["id"]
    stop = threading.Event()

    def drive():
        while not stop.is_set():
            env.rig.tick()
            time.sleep(0.01)

    driver = threading.Thread(target=drive, daemon=True)
    driver.start()
    try:
        body = env.client.get(f"/api/inspections/{id}?wait_s=10").json()
    finally:
        stop.set()
        driver.join()
    assert body["status"] == "done" and body["result"]["outcome"] == "PASS"
    assert env.client.get(f"/api/inspections/{id}?wait_s=31").status_code == 422


def test_pictures_are_kept_even_when_pass_images_are_only_sampled(env):
    env.results.config = RecordingConfig(pass_sample_every=1000)
    body = run_until_done(env, env.client.post("/api/inspections").json()["id"])
    assert body["frame_url"] and env.client.get(body["frame_url"]).status_code == 200


def test_unknown_ids_and_images(env):
    assert env.client.get("/api/inspections/nope").json()["code"] == "inspection_not_found"
    id = env.client.post("/api/inspections").json()["id"]
    assert env.client.get(f"/api/inspections/{id}/frame.jpg").status_code == 404  # not done yet
    assert env.client.get(f"/api/inspections/{id}/thumbnail.jpg").status_code == 404


def test_an_inspection_started_by_the_image_trigger_carries_a_pending_request(env):
    id = env.client.post("/api/inspections", json={"reference": "x"}).json()["id"]
    env.rig.camera.scene = scene_with_object()  # the object arrives in the same moment
    body = run_until_done(env, id)
    assert body["status"] == "done" and body["reference"] == "x"


def test_results_without_a_request_do_not_touch_the_registry(env):
    env.client.post("/api/trigger")
    env.rig.tick(10)
    assert env.recorder.last_record_id and not env.deps.inspections._items


@pytest.mark.parametrize("origin, allowed", [("http://localhost:8800", True), ("http://evil.example", False)])
def test_pages_of_other_programs_listed_in_the_settings_may_call_the_api(env, origin, allowed):
    env.deps.cors_origins = ("http://localhost:8800",)
    client = TestClient(create_app(env.deps))
    r = client.options("/api/inspections", headers={"Origin": origin, "Access-Control-Request-Method": "POST"})
    if allowed:
        assert r.status_code == 200 and r.headers["access-control-allow-origin"] == origin
        assert client.get("/api/state", headers={"Origin": origin}).headers["access-control-allow-origin"] == origin
    else:
        assert r.status_code == 403
