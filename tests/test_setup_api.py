"""The commissioning wizard's state (VIA-0068, FR-ADM-8): derived from what exists, open without a login only
while the Maintainer has no password."""

import json

import pytest

from test_api import env, login  # noqa: F401  (the fixture)
from test_verification import make_bundle
from vision_station.system import SystemConfig, SystemService

ORDER = ["maintainer_password", "camera", "performance", "supervisor_password", "machine", "backup", "first_job"]


def steps(env, headers=None) -> dict[str, dict]:
    r = env.client.get("/api/setup/status", headers=headers or {})
    assert r.status_code == 200, r.text
    return {s["id"]: s for s in r.json()["steps"]}


def forget_maintainer(env):
    """A fresh installation whose installer step for the password was skipped."""
    path = env.auth._file
    users = json.loads(path.read_text())
    del users["maintainer"]
    path.write_text(json.dumps(users))


def test_without_a_maintainer_password_the_status_opens_without_a_login(env):
    forget_maintainer(env)
    r = env.client.get("/api/setup/status")
    assert r.status_code == 200
    body = r.json()
    assert [s["id"] for s in body["steps"]] == ORDER
    assert body["needs_setup"] is True and body["maintainer_password_missing"] is True
    assert body["steps"][0]["state"] == "todo"


def test_with_a_maintainer_password_only_the_maintainer_may_ask(env):
    assert env.client.get("/api/setup/status").status_code == 401
    assert env.client.get("/api/setup/status", headers=login(env, "supervisor")).status_code == 403
    assert env.client.get("/api/setup/status", headers=login(env, "maintainer")).status_code == 200


def test_each_step_is_derived_from_what_exists(env):
    mnt = login(env, "maintainer")
    got = steps(env, mnt)
    assert got["maintainer_password"]["state"] == "done"
    assert got["supervisor_password"]["state"] == "done"
    assert got["camera"]["state"] == "done"  # the station's camera is sending frames
    assert got["first_job"]["state"] == "todo"
    assert got["backup"]["state"] == "todo"  # no folder chosen: backups stay inside the data folder

    env.jobs.save(make_bundle())
    assert steps(env, mnt)["first_job"]["state"] == "done"


def test_a_missing_supervisor_password_or_a_lost_camera_is_a_step_to_do(env):
    path = env.auth._file
    users = json.loads(path.read_text())
    del users["supervisor"]
    path.write_text(json.dumps(users))
    env.rig.camera.fail_read = True  # the frames stop
    env.rig.tick(60)
    got = steps(env, login(env, "maintainer"))
    assert got["supervisor_password"]["state"] == "todo"
    assert got["camera"]["state"] == "todo" and got["camera"]["detail"]


def test_the_backup_step_is_done_when_the_chosen_folder_exists(env, tmp_path):
    folder = tmp_path / "usb"
    env.deps.system = SystemService(tmp_path / "data", SystemConfig.model_validate({"backup": {"folder": str(folder)}}))
    mnt = login(env, "maintainer")
    assert steps(env, mnt)["backup"]["state"] == "todo"  # chosen, but the folder is not there
    folder.mkdir()
    assert steps(env, mnt)["backup"]["state"] == "done"


def test_performance_and_machine_are_unavailable_with_their_reason(env):
    got = steps(env, login(env, "maintainer"))
    assert got["performance"]["state"] == "unavailable" and got["performance"]["detail"]
    assert got["machine"]["state"] == "unavailable" and got["machine"]["detail"]


def test_needs_setup_follows_the_password_the_camera_and_the_job(env):
    mnt = login(env, "maintainer")
    assert env.client.get("/api/setup/status", headers=mnt).json()["needs_setup"] is True  # no job yet
    env.jobs.save(make_bundle())
    body = env.client.get("/api/setup/status", headers=mnt).json()
    assert body["needs_setup"] is False and body["maintainer_password_missing"] is False


def test_the_texts_follow_the_language_asked(env):
    mnt = {**login(env, "maintainer"), "Accept-Language": "en"}
    assert "not available yet" in steps(env, mnt)["machine"]["detail"].lower()


# --- the first password, created in the wizard (S2) -----------------------------------------------------------


@pytest.fixture
def fresh(env, tmp_path):
    """A fresh installation: the Maintainer has no password and the API listens on this PC only."""
    forget_maintainer(env)
    env.deps.system = SystemService(tmp_path / "data", SystemConfig())
    return env


def create_password(env, password="a-good-password"):
    return env.client.put("/api/setup/maintainer-password", json={"password": password})


def test_the_first_password_is_created_without_a_login_and_then_it_logs_in(fresh):
    r = create_password(fresh)
    assert r.status_code == 200 and r.json() == {"role": "maintainer", "has_password": True, "changed_at": r.json()["changed_at"]}
    assert "token" not in r.json()  # no session is opened: the screen logs in afterwards
    assert fresh.client.post("/api/login", json={"role": "maintainer", "password": "a-good-password"}).status_code == 200
    body = fresh.client.get("/api/setup/status", headers=login(fresh, "maintainer", "a-good-password")).json()
    assert body["maintainer_password_missing"] is False


def test_it_works_once_and_then_asks_for_a_login(fresh):
    assert create_password(fresh).status_code == 200
    again = create_password(fresh, "another-password")
    assert again.status_code == 409 and again.json()["code"] == "conflict"
    assert fresh.client.post("/api/login", json={"role": "maintainer", "password": "another-password"}).status_code == 401
    assert fresh.client.post("/api/login", json={"role": "maintainer", "password": "a-good-password"}).status_code == 200


def test_a_short_password_is_refused_and_nothing_changes(fresh):
    r = create_password(fresh, "short")
    assert r.status_code == 400 and r.json()["code"] == "bad_password"
    assert fresh.auth.has_password("maintainer") is False
    assert create_password(fresh).status_code == 200  # the window is still open


def test_it_is_refused_when_the_api_listens_on_the_network(fresh, tmp_path):
    fresh.deps.system = SystemService(tmp_path / "data", SystemConfig.model_validate({"network": {"host": "0.0.0.0"}}))
    r = create_password(fresh)
    assert r.status_code == 403 and r.json()["code"] == "not_local"
    assert fresh.auth.has_password("maintainer") is False


def test_it_is_refused_when_the_system_cannot_say_where_it_listens(fresh):
    fresh.deps.system = None  # fail safe: if the listening address is not known, no password is created without a login
    assert create_password(fresh).status_code == 403


def test_creating_it_is_audited(fresh):
    create_password(fresh)
    events = [e for e in fresh.jobs.read_audit() if e["kind"] == "password_set"]
    assert events and events[-1]["by"] == "setup" and events[-1]["role"] == "maintainer"
    assert "a-good-password" not in json.dumps(fresh.jobs.read_audit())


# --- whether the wizard is open without a login (the operator screen's notice) ---------------------------------


def test_everyone_may_ask_whether_the_wizard_is_open_and_it_says_no_more_than_that(fresh):
    r = fresh.client.get("/api/setup/open")
    assert r.status_code == 200 and r.json() == {"open": True}
    create_password(fresh)
    assert fresh.client.get("/api/setup/open").json() == {"open": False}


def test_the_wizard_is_not_open_on_a_network_api_even_with_no_password(fresh, tmp_path):
    fresh.deps.system = SystemService(tmp_path / "data", SystemConfig.model_validate({"network": {"host": "0.0.0.0"}}))
    assert fresh.client.get("/api/setup/open").json() == {"open": False}  # the notice would lead nowhere: creating is refused
