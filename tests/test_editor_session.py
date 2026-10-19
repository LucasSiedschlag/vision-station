"""The editor's live session (FR-UI-12, document 05 §9.5): the draft on every new frame, with the station paused."""

import json
import threading
import time

import pytest

import vision_station.api.editor_session as session
from test_api import env, login  # noqa: F401
from test_manage_api import draft, mnt  # noqa: F401
from test_verification import qr_scene
from vision_station.station import State


def token_of(headers: dict) -> str:
    return headers["Authorization"].split(" ", 1)[1]


class Running:
    """The station's own thread, for the time the session takes to pause it: in the tests the rig is ticked by hand."""

    def __init__(self, env):
        self.env, self.stop = env, threading.Event()

    def __enter__(self):
        def run():
            while not self.stop.is_set():
                self.env.rig.tick(1)
                time.sleep(0.01)

        self.thread = threading.Thread(target=run, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.stop.set()
        self.thread.join()


def hello(ws, headers, env=None, **extra):
    ws.send_text(json.dumps({"type": "hello", "token": token_of(headers), **extra}))
    if env is None:
        return json.loads(ws.receive_text())
    with Running(env):  # the pause of the station takes the controller thread
        return json.loads(ws.receive_text())


def send_draft(ws, body: dict, **extra):
    ws.send_text(json.dumps({"type": "draft", "job": body["job"], "profile": body["profile"], **extra}))


def next_json(ws, kind: str, limit: int = 20) -> dict:
    """The next text message of this kind; others on the way (a camera notice) are skipped, a frame is not text."""
    for _ in range(limit):
        message = ws.receive()
        if message.get("text") is None:
            continue
        data = json.loads(message["text"])
        if data["type"] == kind:
            return data
    raise AssertionError(f"no {kind} message")


@pytest.fixture
def live(env, mnt):  # noqa: F811
    env.deps.editor_fps = 50  # the tests do not wait a quarter of a second per run
    env.rig.camera.scene = qr_scene("LOTE-1")  # a picture the job can read (the station's own detector never sees it)
    for _ in range(3):
        env.rig.clock.advance(0.1)
        env.rig.acq.step()
    with env.client.websocket_connect("/api/editor/live") as ws:
        ready = hello(ws, mnt, env)
        yield env, ws, mnt, ready


def test_a_page_that_is_not_a_maintainer_is_turned_away_with_a_message(env, mnt):  # noqa: F811
    with env.client.websocket_connect("/api/editor/live") as ws:
        ws.send_text(json.dumps({"type": "hello", "token": "not-a-token"}))
        refused = json.loads(ws.receive_text())
        assert refused["type"] == "error" and refused["code"] == "login_required"
    with env.client.websocket_connect("/api/editor/live") as ws:
        refused = hello(ws, login(env))  # a supervisor may not hold the camera
        assert refused["code"] == "login_required"


def test_the_station_is_paused_while_the_session_lasts_and_resumes_after_it(env, mnt):  # noqa: F811
    env.deps.editor_fps = 50
    assert env.rig.controller.state is not State.PAUSED
    with env.client.websocket_connect("/api/editor/live") as ws:
        ready = hello(ws, mnt, env)
        assert ready["type"] == "ready" and ready["paused_by_session"] is True and ready["fps"] == 50
        env.rig.tick(2)
        assert env.rig.controller.state is State.PAUSED
    env.rig.tick(6)
    assert env.rig.controller.state is not State.PAUSED  # the station is back in production


def test_a_pause_that_was_not_the_sessions_is_not_ended_by_it(env, mnt):  # noqa: F811
    env.deps.editor_fps = 50
    env.rig.controller.pause()  # the person had paused it (Aplicar, Auto uma vez, or the machine monitor)
    env.rig.tick(2)
    with env.client.websocket_connect("/api/editor/live") as ws:
        assert hello(ws, mnt, env)["paused_by_session"] is False
    env.rig.tick(6)
    assert env.rig.controller.state is State.PAUSED


def test_a_station_in_fault_is_left_alone_by_the_session_and_after_it(env, mnt):  # noqa: F811
    """*Tentar de novo* is the person's: closing the editor must not clear a fault by resuming the station."""
    env.deps.editor_fps = 50
    env.rig.controller.fault("a falha de teste")
    env.rig.tick(2)
    assert env.rig.controller.state is State.FAULT
    with env.client.websocket_connect("/api/editor/live") as ws:
        ready = hello(ws, mnt, env)
        assert ready["paused_by_session"] is False and ready["station"] == "Fault"
    env.rig.tick(6)
    assert env.rig.controller.state is State.FAULT


def test_an_inspection_in_progress_ends_before_the_pause_takes_hold(env, mnt):  # noqa: F811
    env.deps.editor_fps = 50
    env.rig.controller.request_trigger()
    env.rig.tick(1)
    assert env.rig.controller.state is State.INSPECTING  # a pause asked now would be dropped: it is asked again
    with env.client.websocket_connect("/api/editor/live") as ws:
        assert hello(ws, mnt, env)["paused_by_session"] is True


def test_the_texts_of_a_result_are_in_the_language_the_socket_asked_for(env, mnt):  # noqa: F811
    """The work is done in a thread of a pool, which does not inherit the language: it must be said there."""
    env.deps.editor_fps = 50
    reasons = {}
    for language in ("pt-BR", "en"):
        with env.client.websocket_connect(f"/api/editor/live?lang={language}") as ws:
            hello(ws, mnt, env)
            send_draft(ws, draft(), add_files=draft()["add_files"])  # the empty scene the station is looking at: not a picture it can use
            reasons[language] = next_json(ws, "result")["result"]["reason"]
    assert reasons["pt-BR"] and reasons["en"] and reasons["pt-BR"] != reasons["en"]
    assert not any(ch in reasons["en"] for ch in "ãõçáéíóú")


def test_the_draft_is_run_on_the_newest_frame_and_the_frame_follows_the_result(live):
    env, ws, mnt, _ = live
    send_draft(ws, draft(), add_files=draft()["add_files"])
    assert next_json(ws, "draft_ok")
    result = next_json(ws, "result")
    assert result["frame_id"] == 1 and result["width"] > 0
    assert [t["id"] for t in result["result"]["tools"]] == ["lote"]
    assert result["result"]["simulated"] is True and result["regions"] and "timings" in result
    jpeg = ws.receive_bytes()
    assert jpeg[:2] == b"\xff\xd8"


def test_a_patch_without_files_changes_the_run_and_a_new_frame_is_measured_again(live):
    env, ws, mnt, _ = live
    body = draft()
    send_draft(ws, body, add_files=body["add_files"])
    first = next_json(ws, "result")
    ws.receive_bytes()
    assert first["result"]["outcome"] in ("PASS", "FAIL", "ERROR")
    body["job"]["tools"][0]["params"] = {"expect": "OUTRO-TEXTO"}  # a patch: only the job
    send_draft(ws, body)
    assert next_json(ws, "draft_ok")
    env.rig.tick(2)
    again = next_json(ws, "result")
    assert again["frame_id"] > first["frame_id"]
    assert again["result"]["outcome"] != "PASS"  # the new limit is in force on the frame


def test_a_refused_draft_is_a_message_and_the_session_goes_on(live):
    env, ws, mnt, _ = live
    bad = draft()
    bad["job"]["tools"][0]["roi"] = "nowhere"
    send_draft(ws, bad, add_files=bad["add_files"])
    refused = next_json(ws, "draft_error")
    assert refused["message"] and refused["fields"] is not None
    good = draft()
    send_draft(ws, good, add_files=good["add_files"])
    assert next_json(ws, "draft_ok")
    assert next_json(ws, "result")["frame_id"] >= 1


def test_only_one_session_at_a_time(live, env, mnt):  # noqa: F811
    _, ws, headers, _ = live
    with env.client.websocket_connect("/api/editor/live") as second:
        busy = hello(second, headers)
        assert busy["type"] == "error" and busy["code"] == "session_busy"


def test_a_camera_that_is_lost_is_told_and_no_frame_is_measured(live):
    env, ws, mnt, _ = live
    send_draft(ws, draft(), add_files=draft()["add_files"])
    next_json(ws, "result")
    ws.receive_bytes()
    env.rig.camera.fail_read = True
    env.rig.tick(3)
    lost = next_json(ws, "camera")
    while lost["connected"]:
        lost = next_json(ws, "camera")
    assert lost["connected"] is False and lost["message"]


def test_a_session_that_hears_nothing_for_a_while_ends_and_says_so(env, mnt, monkeypatch):  # noqa: F811
    env.deps.editor_fps = 50
    monkeypatch.setattr(session, "IDLE_S", 0.3)
    with env.client.websocket_connect("/api/editor/live") as ws:
        hello(ws, mnt, env)
        assert next_json(ws, "idle")
    env.rig.tick(6)
    assert env.rig.controller.state is not State.PAUSED
