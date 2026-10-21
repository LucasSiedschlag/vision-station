"""A job with a pose-based anchor and a real tool, through export and backup to another installation, gives the same
results on its reference set (NFR-REL-5, FR-JOB-5..8, NFR-MAI-3). The store tests use a stub and a code tool; this is the real pipeline."""

import cv2
import numpy as np
import pytest

from test_fixtures_pipeline import job, part_scene
from vision_station.cameras import Frame
from vision_station.core.results import Outcome
from vision_station.pipeline import inspect_job
from vision_station.store import JobBundle, JobRef, JobStore
from vision_station.verification import EXPECTED_FILE, activate, verify_stored_job

from test_verification import expected_yaml


def png(image):
    return cv2.imencode(".png", image)[1].tobytes()


def inspector(bundle, frame):
    return inspect_job(bundle, frame)


def with_reference_set(bundle: JobBundle, version=1) -> JobBundle:
    cases = [
        {"image": "tests/images/straight.png", "outcome": "PASS"},
        {"image": "tests/images/turned.png", "outcome": "PASS"},
        {"image": "tests/images/no-cap.png", "outcome": "FAIL", "reason_contains": "Tampa"},
    ]
    extra = {
        **bundle.extra,
        "tests/images/straight.png": png(part_scene()),
        "tests/images/turned.png": png(part_scene(angle=10.0)),
        "tests/images/no-cap.png": png(part_scene(cap=False)),
        EXPECTED_FILE: expected_yaml(cases),
    }
    meta = bundle.job.job.model_copy(update={"version": version, "parent_version": version - 1 or None})
    return JobBundle(bundle.job.model_copy(update={"job": meta}), bundle.profile, extra)


def outcomes(store: JobStore, ref: JobRef):
    """What the program says of every stored image of the reference set, in the order of the file: outcome, scores, tool values."""
    bundle = store.load(ref)
    found = []
    for name in sorted(k for k in bundle.extra if k.startswith("tests/images/")):
        image = cv2.imdecode(np.frombuffer(bundle.extra[name], np.uint8), cv2.IMREAD_COLOR)
        result = inspector(bundle, Frame(image, 0.0))
        found.append((name, result.outcome, result.scores, result.details.get("tools")))
    return found


@pytest.fixture
def store(tmp_path):
    return JobStore(tmp_path / "bench")


def test_a_backup_restored_on_a_new_installation_gives_the_same_numbers_as_the_original(store, tmp_path):
    ref = store.save(with_reference_set(job()))
    store.set_active(ref)
    assert verify_stored_job(store, ref, inspector).ok

    backup = store.make_backup(tmp_path / "usb")
    new_pc = JobStore(tmp_path / "new-pc")
    restored = new_pc.restore_backup(backup.read_bytes())
    assert restored.active == ref
    report = verify_stored_job(new_pc, ref, inspector)
    assert report.ok, report.failures()
    activate(new_pc, ref, report)

    before, after = outcomes(store, ref), outcomes(new_pc, ref)
    assert [o for _, o, _, _ in before] == [Outcome.FAIL, Outcome.PASS, Outcome.PASS]  # no-cap, straight, turned (sorted by name)
    assert after == before  # outcome, scores and every value of every tool, to the last digit


def test_every_version_in_a_backup_is_restored_and_each_one_verifies(store, tmp_path):
    first = store.save(with_reference_set(job(), version=1))
    second = store.save(with_reference_set(job(), version=2))
    store.set_active(second)

    new_pc = JobStore(tmp_path / "new-pc")
    new_pc.restore_backup(store.make_backup(tmp_path / "usb").read_bytes())
    assert new_pc.versions(first.job_id) == [1, 2]
    for ref in (first, second):  # an old version can still be activated (FR-JOB-5)
        assert verify_stored_job(new_pc, ref, inspector).ok
        assert new_pc.read_files(ref).files == store.read_files(ref).files


def test_a_single_job_file_carries_the_reference_set_with_it(store, tmp_path):
    ref = store.save(with_reference_set(job()))
    other = JobStore(tmp_path / "other")
    other.import_vjob(store.write_vjob(ref, tmp_path / "usb").read_bytes())
    assert verify_stored_job(other, ref, inspector).ok
    assert outcomes(other, ref) == outcomes(store, ref)
