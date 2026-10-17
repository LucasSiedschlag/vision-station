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


def test_on_a_pass_the_margin_is_the_near_miss_not_the_first_criterion():
    from vision_station.core.results import Criterion, ToolReport

    wide = Criterion("min_fraction", "min", True, 1.0, "fraction", 0.9, 0.4)  # far inside
    close = Criterion("max_gap", "max", True, 1.0, "gap", 0.19, 0.2)  # just inside
    t = ToolReport("tampa", "color", 1, True, 1.0, criteria=(wide, close))
    assert t.decisive is close and t.margin == close.margin
    failing = Criterion("min_fraction", "min", False, 0.5, "fraction", 0.2, 0.4)
    assert ToolReport("tampa", "color", 1, False, 0.5, criteria=(close, failing)).decisive is failing


def test_a_tool_with_nothing_to_check_cannot_judge():
    import pytest

    from vision_station.tools.base import ToolError, judged

    with pytest.raises(ToolError):
        judged([])


def test_every_number_given_is_saved_so_a_restart_never_repeats_one():
    saved = []
    rig = Rig(first_sequence=5, save_sequence=saved.append)
    rig.boot()
    rig.controller.request_trigger()
    rig.tick(10)
    assert saved == [5]


def test_the_store_continues_after_the_last_number_given_even_unrecorded(tmp_path):
    from vision_station.records import ResultStore

    with ResultStore(tmp_path) as store:
        store.record(InspectionResult(Outcome.PASS, sequence=3), None, job_id="j", job_name="n", job_version=1)
        store.save_sequence(9)  # given to a result whose recording then failed
    with ResultStore(tmp_path) as store:
        assert store.next_sequence() == 10
