"""The result contract around the pipeline (architecture §10.3, TD-22): sequence, trigger, times, job, simulated."""

import json
from dataclasses import replace

from test_station import Rig, scene_with_object
from vision_station.core.results import InspectionResult, Outcome
from vision_station.store.archive import content_hash


def test_each_result_gets_the_next_sequence_number_and_it_wraps_at_2_32():
    rig = Rig(first_sequence=2**32 - 1)
    rig.boot()
    rig.controller.request_trigger()
    rig.tick(10)
    rig.controller.request_trigger()
    rig.tick(10)
    assert [r.sequence for r in rig.results()][-2:] == [2**32 - 1, 0]


def test_the_trigger_says_what_started_the_inspection():
    rig = Rig()
    rig.boot()
    rig.controller.request_trigger("id-1", "api", "lote 42")
    rig.tick(10)
    api = rig.controller.last_result.trigger
    assert (api.source, api.reference) == ("api", "lote 42") and api.at is not None
    rig.camera.scene = scene_with_object()  # the presence detector starts the next one
    rig.tick(40)
    assert rig.controller.last_result.trigger.source == "image"


def test_times_are_wall_clock_and_the_job_is_named():
    rig = Rig()
    rig.boot()
    rig.controller.request_trigger()
    rig.tick(10)
    r = rig.controller.last_result
    assert r.decided_at is not None and r.decided_at > 1_600_000_000  # epoch seconds, not the monotonic clock
    assert r.acquired_at is not None and r.acquired_at <= r.decided_at
    assert r.job is not None and r.job.version == rig.controller.status().job_version


def test_a_simulated_camera_makes_simulated_results():
    rig = Rig()
    rig.boot()
    rig.acq.simulated = True
    rig.controller.request_trigger()
    rig.tick(10)
    assert rig.controller.last_result.simulated is True


def test_the_content_hash_follows_the_files_and_nothing_else():
    manifest = {"created_at": "a", "files": {"job.yaml": {"sha256": "1" * 64, "size": 3}, "camera/profile.yaml": {"sha256": "2" * 64, "size": 4}}}
    same = {**manifest, "created_at": "b", "app_version": "9"}
    other = json.loads(json.dumps(manifest))
    other["files"]["job.yaml"]["sha256"] = "3" * 64
    assert content_hash(manifest) == content_hash(same) != content_hash(other)


def test_the_controller_keeps_the_pipeline_fields():
    def inspect(frame):
        return InspectionResult(Outcome.ERROR, "x", error_code=104)

    rig = Rig(outcome=inspect)
    rig.boot()
    rig.controller.request_trigger()
    rig.tick(10)
    assert rig.controller.last_result.error_code == 104 and rig.controller.last_result.sequence == 0
    assert replace(rig.controller.last_result, sequence=None).error_code == 104
