from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from vision_station.jobs import CameraProfile, Job, acquisition_block, dump_job, parse_job

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
        lambda d: d.update(format=1),  # an older format is no longer read (nothing is deployed, TD-21)
        lambda d: d.update(format=2),
        lambda d: d.update(format=4),
        lambda d: d.update(surprise=1),  # unknown fields are typos, not extensions
        lambda d: d["job"].update(parent_version=7),
        lambda d: d["acquisition"]["trigger"]["image_presence"].update(roi=[0.9, 0.1, 0.1, 0.9]),
        lambda d: d["acquisition"]["trigger"]["image_presence"].update(roi=[0.1, 0.1, 1.5, 0.9]),
        lambda d: d["quality"]["brightness"].update(min=200),
        lambda d: d["geometry"]["rois"].update(anchor={"relative_to": "frame", "rect": [0, 0, 1, 1]}),
        lambda d: d["tools"][0].update(roi="nowhere"),
        lambda d: d["tools"][1].update(id="tampa"),
        lambda d: d.update(tools=[]),
        lambda d: d["acquisition"]["trigger"].pop("image_presence"),  # the type needs its block
        lambda d: d["acquisition"]["trigger"]["image_presence"].pop("diff_threshold"),  # written in full (FR-JOB-16)
        lambda d: d["acquisition"]["trigger"].update(type="sometimes"),
        lambda d: d["acquisition"].pop("image"),
        lambda d: d["acquisition"]["image"].update(profile=3),
        lambda d: d.pop("acquisition"),
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
        lambda d: d.pop("orientation"),  # a profile is written in full (FR-JOB-16)
        lambda d: d.pop("power_line_hz"),
        lambda d: d.pop("low_light_compensation"),
        lambda d: d.pop("zoom"),
        lambda d: d["exposure"].pop("auto_once"),
        lambda d: d["exposure"]["auto_once"].pop("region"),
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


def test_the_type_decides_which_block_of_the_trigger_is_needed_and_the_others_may_stay():
    data = load_job_data()
    data["acquisition"]["trigger"] = {"type": "manual"}
    assert Job.model_validate(data).acquisition.trigger.type == "manual"  # a manual trigger has nothing to write
    for kind in ("external", "continuous"):
        data["acquisition"] = acquisition_block(kind)
        job = Job.model_validate(data)
        assert job.acquisition.trigger.type == kind and getattr(job.acquisition.trigger, kind) is not None
        data["acquisition"]["trigger"]["type"] = "manual"  # switching the type keeps what was typed, and ignores it
        assert Job.model_validate(data).acquisition.trigger.type == "manual"
    with pytest.raises(ValidationError):
        data["acquisition"]["trigger"] = {"type": "external"}  # the type's own block is missing
        Job.model_validate(data)


def test_screen_text_is_optional_and_comes_from_the_job():
    data = load_job_data()
    assert Job.model_validate(data).ui.waiting.get("pt-BR") == "Aguardando peça"
    del data["ui"]
    assert Job.model_validate(data).ui.waiting is None


def test_the_blocks_are_written_in_full_and_their_limits_are_checked():
    """FR-JOB-16: what the job means is in the file, and the software has no defaults of its own to change it."""
    base = load_job_data()
    base["acquisition"] = acquisition_block("continuous", external={"delay_ms": 20, "debounce_ms": 5})
    job = Job.model_validate(base)
    text = dump_job(job)
    assert "interval_ms: 500" in text and "delay_ms: 20" in text and "debounce_ms: 5" in text and "calibration: null" in text
    assert parse_job(text) == job
    for block, field, bad in (("continuous", "interval_ms", -1), ("continuous", "interval_ms", 10_001), ("external", "delay_ms", 1001), ("external", "debounce_ms", 66), ("external", "delay_ms", -1)):
        broken = load_job_data()
        broken["acquisition"] = acquisition_block("continuous", external={"delay_ms": 20, "debounce_ms": 5})
        broken["acquisition"]["trigger"][block][field] = bad
        with pytest.raises(ValidationError):
            Job.model_validate(broken)
    assert acquisition_block("manual")["trigger"] == {"type": "manual"}


def _grouped(data: dict, members=("tampa", "defeitos")) -> dict:
    """The sample job with `members` in one group of which one passing tool is enough (TD-33)."""
    data["groups"] = {"marca": {"reason_fail": {"pt-BR": "Sem tampa nem defeito lido", "en": "No cap and no defect read"}}}
    for tool in data["tools"]:
        if tool["id"] in members:
            tool["group"] = "marca"
    return data


def test_a_group_of_tools_is_read_and_round_trips():
    job = Job.model_validate(_grouped(load_job_data()))
    assert [t.group for t in job.tools] == ["marca", "marca"]
    assert job.groups["marca"].reason_fail.get("en") == "No cap and no defect read"
    assert parse_job(dump_job(job)) == job


def test_groups_are_written_only_when_used():
    """TD-33: a job without a group is the same file as before, so a program that does not know groups still reads it."""
    written = yaml.safe_load(dump_job(Job.model_validate(load_job_data())))
    assert "groups" not in written and all("group" not in tool for tool in written["tools"])
    grouped = yaml.safe_load(dump_job(Job.model_validate(_grouped(load_job_data()))))
    assert list(grouped["groups"]) == ["marca"] and grouped["tools"][0]["group"] == "marca"


@pytest.mark.parametrize(
    "change",
    [
        lambda d: d["tools"][0].update(group="marca"),  # a group nobody declared
        lambda d: d.update(groups={"marca": {"reason_fail": "x"}}),  # a group no tool uses
        lambda d: _grouped(d, members=("tampa",)),  # a group of one is not an OR
        lambda d: (_grouped(d), d["tools"][1].update(affects_result=False)),  # an informative tool never decides
        lambda d: (_grouped(d), d["groups"]["marca"].pop("reason_fail")),  # a failed group says its own text
        lambda d: (_grouped(d), d["groups"].update(outra={"reason_fail": "x"})),  # a second group no tool uses
        lambda d: (_grouped(d), d["groups"].update({"": {"reason_fail": "x"}})),
        lambda d: (_grouped(d), d["groups"]["marca"].update(surprise=1)),
        lambda d: (_grouped(d), d["tools"][0].update(group="")),
    ],
)
def test_invalid_groups_are_rejected(change):
    data = load_job_data()
    change(data)
    with pytest.raises(ValidationError):
        Job.model_validate(data)
