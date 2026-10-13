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
    assert job.job.name == "Caixa M — fita vermelha"
    assert job.job.version == 7
    assert [c.id for c in job.checks] == ["tape", "closed"]
    assert job.geometry.rois["seam"].relative_to == "box"


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
        lambda d: d.update(format=2),
        lambda d: d.update(surprise=1),  # unknown fields are typos, not extensions
        lambda d: d["job"].update(parent_version=7),
        lambda d: d["trigger"].update(presence_roi=[0.9, 0.1, 0.1, 0.9]),
        lambda d: d["trigger"].update(presence_roi=[0.1, 0.1, 1.5, 0.9]),
        lambda d: d["quality"]["brightness"].update(min=200),
        lambda d: d["geometry"]["rois"].update(box={"relative_to": "frame", "rect": [0, 0, 1, 1]}),
        lambda d: d["checks"][0].update(roi="nowhere"),
        lambda d: d["checks"][1].update(id="tape"),
        lambda d: d.update(checks=[]),
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
