import io
import json
import logging
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import cv2
import numpy as np
import pytest

from test_station import Rig, State, empty_scene, scene_with_object
from vision_station.records import (
    Query,
    RecordingConfig,
    ResultRecorder,
    ResultsError,
    ResultStore,
)
from vision_station.core.results import InspectionResult, Outcome

JOB = {"job_id": "3f1c9a2e-5b7d-4c1e-9a0f-2d6b8e4f7a10", "job_name": "Tampa azul", "job_version": 3}
OTHER = {"job_id": "9b2d4c60-1a3e-4f5b-8c7d-0e1f2a3b4c5d", "job_name": "Etiqueta", "job_version": 1}
TZ = timezone(timedelta(hours=-3))


class Clock:
    """Starts on 2026-10-14 08:00 and moves one minute on every call."""

    def __init__(self):
        self.t = datetime(2026, 10, 14, 8, 0, tzinfo=TZ)

    def __call__(self):
        self.t += timedelta(minutes=1)
        return self.t

    def jump(self, **kw):
        self.t += timedelta(**kw)


def frame(value=120, size=(48, 64)):
    img = np.zeros((*size, 3), np.uint8)
    img[:] = value
    img[10:20, 10:30] = 255 - value  # something to see
    return img


def res(outcome=Outcome.PASS, reason="", **kw):
    return InspectionResult(outcome, reason, **kw)


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def store(tmp_path, clock):
    with ResultStore(tmp_path / "data", clock=clock) as s:
        yield s


# --- recording -----------------------------------------------------------------


def test_a_result_is_recorded_with_everything_the_requirement_lists(store):
    r = store.record(
        res(Outcome.FAIL, "Tampa fora da cor em 40% da área", scores={"tampa": 0.6}, duration_s=0.42, details={"timings": {"locate": 0.1, "tools": 0.3}}),
        frame(),
        **JOB,
    )
    assert r.outcome == "FAIL" and r.reason.startswith("Tampa fora da cor")
    assert (r.job_name, r.job_version, r.job_id) == ("Tampa azul", 3, JOB["job_id"])
    assert r.scores == {"tampa": 0.6} and r.timings == {"locate": 0.1, "tools": 0.3}
    assert r.duration_ms == pytest.approx(420)
    assert r.at.startswith("2026-10-14T08:") and r.at.endswith("-03:00")
    assert r.image_path.startswith("results/images/2026/10/14/") and r.image_path.endswith(".jpg")
    assert store.get(r.id) == r and store.get("missing") is None


def test_the_raw_image_is_kept_apart_from_the_overlay(store):
    raw = frame()
    marked = raw.copy()
    cv2.rectangle(marked, (0, 0), (60, 40), (0, 0, 255), 2)
    r = store.record(res(Outcome.FAIL, "x"), raw, overlay=marked, **JOB)
    assert r.overlay_path.endswith(f"{r.id}.overlay.jpg") and r.overlay_path != r.image_path
    saved = cv2.imread(str(store.root / r.image_path))
    drawn = cv2.imread(str(store.root / r.overlay_path))
    assert saved.shape == raw.shape and np.abs(saved.astype(int) - raw.astype(int)).mean() < 6  # still the clean frame (JPEG loss only)
    assert np.abs(drawn.astype(int) - saved.astype(int)).mean() > 1  # the overlay differs


def test_an_error_without_a_frame_is_recorded_without_an_image(store):
    r = store.record(res(Outcome.ERROR, "Câmera desconectada durante a inspeção"), None, **JOB)
    assert r.image_path is None and r.outcome == "ERROR"


def test_by_default_every_image_is_kept(store):
    records = [store.record(res(), frame(), **JOB) for _ in range(5)]
    assert all(r.sampled and (store.root / r.image_path).is_file() for r in records)


def test_pass_sampling_flags_one_in_n_and_housekeeping_drops_the_rest_after_the_hours(tmp_path, clock):
    cfg = RecordingConfig(pass_sample_every=3, unsampled_pass_hours=1)
    with ResultStore(tmp_path / "d", config=cfg, clock=clock) as s:
        passes = [s.record(res(), frame(i), **JOB) for i in range(6)]
        fail = s.record(res(Outcome.FAIL, "x"), frame(), **JOB)
        assert [p.sampled for p in passes] == [False, False, True, False, False, True]
        assert fail.sampled
        assert s.housekeeping() == {"records": 0, "images": 0}  # too recent
        clock.jump(hours=2)
        assert s.housekeeping()["images"] == 4
        after = {r.id: r for r in s.find(limit=50)}
        assert [after[p.id].image_path is not None for p in passes] == [False, False, True, False, False, True]
        assert after[fail.id].image_path is not None
        assert s.count() == 7  # the rows stay, only images go


def test_a_failure_while_recording_leaves_no_row_and_no_file(store, monkeypatch):
    monkeypatch.setattr(store, "_collecting", lambda job_id: (_ for _ in ()).throw(OSError("disk full")))
    with pytest.raises(OSError):
        store.record(res(Outcome.FAIL, "x"), frame(), overlay=frame(), **JOB)
    assert store.count() == 0
    assert not [p for p in (store.root / "results" / "images").rglob("*") if p.is_file()]


def test_recording_from_several_threads(store):
    errors = []

    def work():
        try:
            for _ in range(25):
                store.record(res(), frame(), **JOB)
        except Exception as exc:  # pragma: no cover
            errors.append(exc)

    threads = [threading.Thread(target=work) for _ in range(4)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert not errors and store.count() == 100


# --- queries -------------------------------------------------------------------


@pytest.fixture
def filled(store, clock):
    ids = {}
    ids["p1"] = store.record(res(), frame(), **JOB).id
    ids["f1"] = store.record(res(Outcome.FAIL, "a"), frame(), **JOB).id
    clock.jump(days=1)
    ids["p2"] = store.record(res(), frame(), **OTHER).id
    ids["e1"] = store.record(res(Outcome.ERROR, "b"), None, **OTHER).id
    return ids


def test_find_filters_orders_and_pages(store, filled):
    assert [r.id for r in store.find()] == [filled[k] for k in ("e1", "p2", "f1", "p1")]  # newest first
    assert {r.id for r in store.find(Query(job_id=JOB["job_id"]))} == {filled["p1"], filled["f1"]}
    assert [r.id for r in store.find(Query(outcome="FAIL"))] == [filled["f1"]]
    day1 = datetime(2026, 10, 14, tzinfo=TZ)
    assert store.count(Query(since=day1, until=day1 + timedelta(days=1))) == 2
    assert store.count(Query(since=day1 + timedelta(days=1))) == 2
    assert [r.id for r in store.find(limit=2, offset=1)] == [filled["p2"], filled["f1"]]
    assert store.count() == 4


def test_counts_for_a_shift(store, filled):
    day2 = datetime(2026, 10, 15, tzinfo=TZ)
    assert store.counts(day2 - timedelta(days=5)) == {"PASS": 2, "FAIL": 1, "ERROR": 1, "total": 4}
    assert store.counts(day2) == {"PASS": 1, "FAIL": 0, "ERROR": 1, "total": 2}
    assert store.counts(day2, job_id=JOB["job_id"])["total"] == 0


def test_csv_export(store, filled, tmp_path):
    path = tmp_path / "out.csv"
    assert store.export_csv(path) == 4
    raw = path.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")  # BOM, so Excel reads the accents
    lines = raw.decode("utf-8-sig").splitlines()
    assert lines[0].startswith("id;data_hora;job;versao;resultado;motivo")
    assert len(lines) == 5 and any("Etiqueta;1;ERROR;b" in line for line in lines)
    buffer = io.StringIO()
    assert store.export_csv(buffer, Query(outcome="PASS")) == 2
    assert buffer.getvalue().count("\n") == 3


# --- collection mode and corrections -------------------------------------------


def test_collection_mode_saves_every_frame_for_the_job_that_asks(store):
    assert not store.collecting(JOB["job_id"])
    store.record(res(), frame(), **JOB)
    assert store.dataset_count() == 0
    store.set_collection(JOB["job_id"], True)
    a = store.record(res(), frame(1), **JOB)
    b = store.record(res(Outcome.FAIL, "x"), frame(2), **JOB)
    store.record(res(), frame(3), **OTHER)  # another job: not collected
    assert store.collecting(JOB["job_id"]) and store.dataset_count() == 2 and store.dataset_count(JOB["job_id"]) == 2
    assert (store.root / "dataset" / JOB["job_id"] / f"{a.id}.jpg").is_file()
    store.set_collection(JOB["job_id"], False)
    store.record(res(), frame(4), **JOB)
    assert store.dataset_count() == 2
    assert b.id


def test_a_wrong_result_goes_to_the_dataset_with_the_right_label(store):
    r = store.record(res(), frame(), **JOB)
    fixed = store.mark_incorrect(r.id, "FAIL", by="supervisor")
    assert fixed.correct_outcome == "FAIL" and fixed.corrected_by == "supervisor" and fixed.corrected_at
    assert fixed.outcome == "PASS"  # what the system said is kept
    assert store.dataset_count() == 1 and store.count(Query(incorrect_only=True)) == 1
    export = store.export_dataset(store.root / "out")
    labels = (export.path / "labels.csv").read_text(encoding="utf-8").splitlines()
    assert labels[1].split(",")[4:7] == ["PASS", "FAIL", "corrected"]


def test_corrections_that_cannot_work_are_refused(store):
    r = store.record(res(), None, **JOB)  # no image
    with pytest.raises(ResultsError, match="not kept"):
        store.mark_incorrect(r.id, "FAIL")
    with pytest.raises(ResultsError, match="no such result"):
        store.mark_incorrect("nope", "FAIL")
    with pytest.raises(ResultsError, match="PASS or FAIL"):
        store.mark_incorrect(r.id, "MAYBE")


def test_dataset_export_has_a_manifest_and_a_content_based_id(store, tmp_path):
    with pytest.raises(ResultsError, match="empty"):
        store.export_dataset(tmp_path / "out")
    store.set_collection(JOB["job_id"], True)
    for i in range(3):
        store.record(res(), frame(i * 10), **JOB)
    first = store.export_dataset(tmp_path / "out")
    manifest = json.loads((first.path / "manifest.json").read_text())
    assert manifest["count"] == 3 and manifest["dataset_id"] == first.dataset_id
    import hashlib

    for name, digest in manifest["files"].items():
        assert hashlib.sha256((first.path / name).read_bytes()).hexdigest() == digest
    assert "labels.csv" in manifest["files"] and len([n for n in manifest["files"] if n.startswith("images/")]) == 3
    assert store.export_dataset(tmp_path / "out").path == first.path  # same content, same folder
    store.record(res(), frame(99), **JOB)
    assert store.export_dataset(tmp_path / "out").dataset_id != first.dataset_id


# --- housekeeping --------------------------------------------------------------


def test_retention_deletes_old_records_and_their_images_but_never_the_dataset(tmp_path, clock):
    cfg = RecordingConfig(retention_days=30)
    with ResultStore(tmp_path / "d", config=cfg, clock=clock) as s:
        s.set_collection(JOB["job_id"], True)
        old = s.record(res(Outcome.FAIL, "x"), frame(), **JOB)
        clock.jump(days=20)
        recent = s.record(res(), frame(), **JOB)
        clock.jump(days=20)  # the first is now 40 days old
        assert s.housekeeping() == {"records": 1, "images": 1}
        assert s.get(old.id) is None and s.get(recent.id) is not None
        assert not (s.root / old.image_path).exists() and (s.root / recent.image_path).exists()
        assert s.dataset_count() == 2 and (s.root / "dataset" / JOB["job_id"] / f"{old.id}.jpg").is_file()


def test_low_disk_deletes_pass_images_first_then_fail_and_spares_corrected_ones(tmp_path, clock):
    with ResultStore(tmp_path / "d", config=RecordingConfig(min_free_bytes=7000), clock=clock) as s:
        passes = [s.record(res(), frame(i), **JOB) for i in range(4)]
        fails = [s.record(res(Outcome.FAIL, "x"), frame(i), **JOB) for i in range(2)]
        s.mark_incorrect(passes[0].id, "FAIL")  # corrected: it is training data, so it is kept
        images = lambda: list((s.root / "results" / "images").rglob("*.jpg"))
        total = len(images())
        s._disk_free = lambda root: 3000 * (total - len(images()))  # every deleted image frees 3000 bytes
        assert s.housekeeping()["images"] == 3  # 9000 >= 7000 after the third: stops there
        left = {r.id: r.image_path is not None for r in s.find(limit=50)}
        assert left[passes[0].id] and not any(left[p.id] for p in passes[1:])  # the oldest PASS images went first
        assert all(left[f.id] for f in fails)  # no FAIL image was needed
        s._disk_free = lambda root: 0  # a limit that can never be met
        s.housekeeping()
        left = {r.id: r.image_path is not None for r in s.find(limit=50)}
        assert left[passes[0].id] and not any(left[f.id] for f in fails)  # FAIL images follow; the corrected one stays


# --- with the station ----------------------------------------------------------


def test_the_station_records_each_result_with_its_job_and_frame(tmp_path):
    with ResultStore(tmp_path / "d") as s:
        recorder = ResultRecorder(s)
        rig = Rig()
        rig.controller._on_event = recorder
        rig.boot()
        rig.camera.scene = scene_with_object(40)
        rig.tick(10)
        rig.camera.scene = empty_scene()
        rig.tick(6)
        rig.camera.scene = scene_with_object(60)
        rig.tick(12)
        rows = s.find()
        assert len(rows) == 2 and recorder.failures == 0
        assert {(r.job_name, r.job_version) for r in rows} == {("Tampa azul — etiqueta de lote", 7)}
        assert all(r.image_path and (s.root / r.image_path).is_file() and r.outcome == "PASS" for r in rows)


def test_a_failing_recorder_or_handler_does_not_stop_the_station(tmp_path, caplog):
    s = ResultStore(tmp_path / "d")
    recorder = ResultRecorder(s)
    s.close()  # every record() from now on raises
    rig = Rig()
    rig.controller._on_event = recorder
    rig.boot()
    rig.camera.scene = scene_with_object(40)
    with caplog.at_level(logging.ERROR):
        rig.tick(10)
    assert rig.state is State.SHOWING_RESULT and recorder.failures == 1 and "ProgrammingError" in recorder.last_error
    rig2 = Rig()
    rig2.controller._on_event = lambda event: 1 / 0
    rig2.boot()
    rig2.camera.scene = scene_with_object(40)
    rig2.tick(10)
    assert rig2.state is State.SHOWING_RESULT


# --- the result contract (version 2, TD-22, FR-LOG-8) --------------------------------------------------

V1_SCHEMA = """
CREATE TABLE inspections (
    id TEXT PRIMARY KEY, at TEXT NOT NULL, at_epoch REAL NOT NULL, job_id TEXT NOT NULL, job_name TEXT NOT NULL,
    job_version INTEGER NOT NULL, outcome TEXT NOT NULL, reason TEXT NOT NULL, scores TEXT NOT NULL,
    timings TEXT NOT NULL, duration_ms REAL NOT NULL, image_path TEXT, overlay_path TEXT,
    sampled INTEGER NOT NULL DEFAULT 1, correct_outcome TEXT, corrected_at TEXT, corrected_by TEXT
);
INSERT INTO inspections VALUES ('old-1', '2026-10-13T08:00:00.000-03:00', 1792000000, 'j', 'Tampa', 1, 'ERROR',
    'Câmera desconectada durante a inspeção', '{}', '{}', 12.0, NULL, NULL, 1, NULL, NULL, NULL);
PRAGMA user_version=1;
"""


def test_a_database_of_version_1_is_migrated_and_its_old_rows_still_read(tmp_path, clock):
    import sqlite3

    (tmp_path / "results").mkdir()
    db = sqlite3.connect(tmp_path / "results" / "results.db")
    db.executescript(V1_SCHEMA)
    db.close()
    with ResultStore(tmp_path, clock=clock) as store:
        old = store.get("old-1")
        assert old.outcome == "ERROR" and old.error_code is None and old.sequence is None  # unknown, never 0
        assert old.tools == () and old.trigger is None and old.simulated is None  # not known before the contract
        new = store.record(res(Outcome.ERROR, "x", error_code=401, sequence=7), None, **JOB)
        assert store.get(new.id).error_code == 401 and store.next_sequence() == 8
    db = sqlite3.connect(tmp_path / "results" / "results.db")
    assert db.execute("PRAGMA user_version").fetchone()[0] == 2
    db.execute("PRAGMA user_version=1")  # a program of version 1 opened it in between
    db.commit()
    db.close()
    with ResultStore(tmp_path, clock=clock) as store:  # the columns are there already: no second ALTER
        assert store.get(new.id).error_code == 401


def test_the_contract_is_recorded_and_read_back(tmp_path, clock):
    from vision_station.core.results import Criterion, FixturePose, ReasonCode, ResultJob, ToolReport, TriggerInfo

    tool = ToolReport("tampa", "color", 1, False, 0.5, {"fraction": 0.4}, {"fraction": "fraction"},
                      (Criterion("min_fraction", "min", False, 0.5, "fraction", 0.4, 0.8),))
    result = res(
        Outcome.FAIL, "Tampa ausente", sequence=41, reason_codes=(ReasonCode("tampa", "color.min_fraction"),), tools=(tool,),
        fixtures=(FixturePose("anchor", 0.5, 0.5, None, None, 0.9),), trigger=TriggerInfo("api", "lote 42", at=1.0),
        job=ResultJob("j", "Tampa", 3, content_hash="ab" * 32), acquired_at=1.5, decided_at=2.0, simulated=True,
    )
    with ResultStore(tmp_path, clock=clock) as store:
        r = store.get(store.record(result, None, **JOB).id)
        assert (r.sequence, r.error_code, r.simulated, r.job_hash) == (41, 0, True, "ab" * 32)
        assert r.reason_codes == ({"tool": "tampa", "code": "color.min_fraction"},)
        (t,) = r.tools
        assert t["criteria"][0]["margin"] == pytest.approx(-0.4) and t["margin"] == pytest.approx(-0.4)
        assert r.fixtures[0]["angle"] is None and r.trigger["source"] == "api" and r.trigger["reference"] == "lote 42"
        assert (r.acquired_at, r.decided_at) == (1.5, 2.0)
        out = io.StringIO()
        store.export_csv(out)
        header, row = out.getvalue().splitlines()[:2]
        assert header.endswith("sequencia;codigo_erro;codigos_motivo;simulado")
        assert row.endswith("41;0;tampa:color.min_fraction;1")


def test_the_sequence_continues_after_a_restart(tmp_path, clock):
    with ResultStore(tmp_path, clock=clock) as store:
        assert store.next_sequence() == 0
        store.record(res(sequence=2**32 - 1), None, **JOB)
    with ResultStore(tmp_path, clock=clock) as store:
        assert store.next_sequence() == 0  # wraps like the controller
        store.record(res(sequence=0), None, **JOB)
        assert store.next_sequence() == 1


def test_results_are_filtered_by_reason_code_and_the_codes_on_offer_follow_the_other_filters(store):
    """FR-INS-14: the supervisor finds the failures of one criterion; the options are what the other filters leave."""
    from vision_station.core.results import ReasonCode

    def fail(code, tool="t"):
        return res(Outcome.FAIL, "x", reason_codes=(ReasonCode(tool, code),))

    store.record(fail("color.min_fraction"), frame(), **JOB)
    store.record(fail("color.min_fraction"), frame(), **JOB)
    store.record(fail("code.min_count", "c"), frame(), **JOB)
    store.record(res(Outcome.PASS), frame(), **JOB)
    other = {**JOB, "job_id": "other", "job_name": "Outra"}
    store.record(fail("pattern.min_score", "p"), frame(), **other)
    assert store.count(Query(reason_code="color.min_fraction")) == 2
    assert [r.reason_codes[0]["code"] for r in store.find(Query(reason_code="code.min_count"))] == ["code.min_count"]
    assert store.count(Query(reason_code="nothing.here")) == 0
    assert store.count(Query(reason_code="color.min_fraction", outcome="PASS")) == 0  # together with the other filters
    assert store.reason_codes() == [("color.min_fraction", 2), ("code.min_count", 1), ("pattern.min_score", 1)]
    assert store.reason_codes(Query(job_id=JOB["job_id"], reason_code="code.min_count")) == [("color.min_fraction", 2), ("code.min_count", 1)]  # its own filter does not hide the others
    out = io.StringIO()
    store.export_csv(out, Query(reason_code="code.min_count"))
    assert len(out.getvalue().splitlines()) == 2


def test_the_dataset_lists_the_images_of_a_job_with_their_labels(store):
    store.set_collection(JOB["job_id"], True)
    store.record(res(Outcome.PASS), frame(), **JOB)
    wrong = store.record(res(Outcome.PASS), frame(), **JOB)
    store.mark_incorrect(wrong.id, "FAIL", by="supervisor")
    items = store.dataset_items(JOB["job_id"])
    assert {(i["source"], i["label"]) for i in items} == {("collected", None), ("corrected", "FAIL")}
    assert store.dataset_items(JOB["job_id"], limit=1, offset=1) != store.dataset_items(JOB["job_id"], limit=1, offset=0)
    assert store.dataset_items("other") == []
    path = store.dataset_file(JOB["job_id"], items[0]["id"])
    assert path is not None and path.suffix == ".jpg"
    assert store.dataset_file("other", items[0]["id"]) is None  # an id of another job is not its image
