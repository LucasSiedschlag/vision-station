from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from vision_station.jobs import CameraProfile, Job, dump_job, parse_job

FIXTURES = Path(__file__).parent / "fixtures"


def load_job_data() -> dict:
    return yaml.safe_load((FIXTURES / "job.yaml").read_text(encoding="utf-8"))


def test_architecture_example_job_is_valid():
    job = parse_job((FIXTURES / "job.yaml").read_text(encoding="utf-8"))
    assert job.job.name == "Tampa azul — etiqueta de lote"
    assert job.job.version == 7
    assert [t.id for t in job.tools] == ["tampa", "defeitos"]
    assert job.geometry.rois["cap"].relative_to == "anchor"


def test_job_round_trips_through_yaml():
    job = parse_job((FIXTURES / "job.yaml").read_text(encoding="utf-8"))
    assert parse_job(dump_job(job)) == job


def test_architecture_example_profile_is_valid():
    data = yaml.safe_load((FIXTURES / "profile.yaml").read_text(encoding="utf-8"))
    profile = CameraProfile.model_validate(data)
    assert profile.resolution == (1920, 1080)
    assert profile.exposure.value_us == 8000


@pytest.mark.parametrize(
    "change",
    [
        lambda d: d.update(format=1),  # the first format is no longer read (nothing is deployed, TD-21)
        lambda d: d.update(format=3),
        lambda d: d.update(surprise=1),  # unknown fields are typos, not extensions
        lambda d: d["job"].update(parent_version=7),
        lambda d: d["trigger"].update(presence_roi=[0.9, 0.1, 0.1, 0.9]),
        lambda d: d["trigger"].update(presence_roi=[0.1, 0.1, 1.5, 0.9]),
        lambda d: d["quality"]["brightness"].update(min=200),
        lambda d: d["geometry"]["rois"].update(anchor={"relative_to": "frame", "rect": [0, 0, 1, 1]}),
        lambda d: d["tools"][0].update(roi="nowhere"),
        lambda d: d["tools"][1].update(id="tampa"),
        lambda d: d.update(tools=[]),
        lambda d: d["trigger"].update(mode="image_presence", presence_roi=None),
        lambda d: d["trigger"].update(mode="sometimes"),
        lambda d: d["geometry"].update(fixtures=[]),  # ROIs and tools still refer to the anchor
    ],
)
def test_invalid_jobs_are_rejected(change):
    data = load_job_data()
    change(data)
    with pytest.raises(ValidationError):
        Job.model_validate(data)


@pytest.mark.parametrize(
    "change",
    [
        lambda d: d.update(exposure={"mode": "manual"}),
        lambda d: d.update(exposure={"mode": "auto", "value_us": 8000}),
        lambda d: d.update(white_balance={"mode": "manual"}),
        lambda d: d.update(gain={"mode": "manual"}),
        lambda d: d.update(resolution=[0, 1080]),
        lambda d: d.update(power_line_hz=55),
    ],
)
def test_invalid_profiles_are_rejected(change):
    data = yaml.safe_load((FIXTURES / "profile.yaml").read_text(encoding="utf-8"))
    change(data)
    with pytest.raises(ValidationError):
        CameraProfile.model_validate(data)


def test_job_without_locator_works_on_the_frame():
    data = load_job_data()
    data["geometry"] = {"rois": {"label": {"relative_to": "frame", "rect": [0.2, 0.2, 0.8, 0.5]}}}
    data["tools"] = [
        {"id": "read", "type": "code", "version": 1, "roi": "label", "reason_fail": "Código não lido"}
    ]
    job = Job.model_validate(data)
    assert job.geometry.fixtures == []


def test_trigger_modes_that_need_no_presence_settings():
    data = load_job_data()
    for mode in ("manual", "external", "continuous"):
        data["trigger"] = {"mode": mode}
        assert Job.model_validate(data).trigger.mode == mode


def test_screen_text_is_optional_and_comes_from_the_job():
    data = load_job_data()
    assert Job.model_validate(data).ui.waiting.get("pt-BR") == "Aguardando peça"
    del data["ui"]
    assert Job.model_validate(data).ui.waiting is None


def test_the_continuous_interval_is_500_ms_unless_set_and_is_written_only_when_changed():
    base = load_job_data()
    job = Job.model_validate(base)
    assert job.trigger.interval_ms == 500 and "interval_ms" not in dump_job(job)  # still opens in a version without it
    base["trigger"] = {**base["trigger"], "interval_ms": 0}
    assert "interval_ms: 0" in dump_job(Job.model_validate(base))
    for bad in (-1, 10_001):
        with pytest.raises(ValidationError):
            Job.model_validate({**base, "trigger": {**base["trigger"], "interval_ms": bad}})
