"""A part that arrives turned is judged as one that arrives straight, and one that is too far from what was taught is ERROR (FR-INS-11, FR-INS-12, TD-21)."""

import cv2
import numpy as np
import pytest
import yaml

from test_locators import BENCH, CAP, PART, FIXTURES
from vision_station.cameras import Frame
from vision_station.core.i18n import render
from vision_station.core.results import Outcome
from vision_station.jobs import CameraProfile, Job, dump_job, parse_job
from vision_station.pipeline import draw_overlay, inspect_job
from vision_station.store import JobBundle
from vision_station.verification import make_reference_files

W, H = 640, 480
TAUGHT = [160, 90]  # the part as taught: 160 x 90 px, centred at (320, 240)


def part_scene(angle=0.0, scale=1.0, at=(320.0, 240.0), cap=True):
    """A dark part with a blue cap along its top edge, on a light bench, turned counter-clockwise by `angle` degrees."""
    image = np.full((H, W, 3), BENCH, np.uint8)
    cx, cy = 320, 240
    image[cy - 45 : cy + 45, cx - 80 : cx + 80] = PART
    if cap:
        image[cy - 45 : cy - 25, cx - 40 : cx + 40] = CAP  # 80 x 20 px at the top
    matrix = cv2.getRotationMatrix2D((320.0, 240.0), angle, scale)
    matrix[:, 2] += (at[0] - 320.0, at[1] - 240.0)
    return cv2.warpAffine(image, matrix, (W, H), flags=cv2.INTER_LINEAR, borderValue=BENCH)


def job(**changes):
    data = yaml.safe_load((FIXTURES / "job.yaml").read_text(encoding="utf-8"))
    data["quality"] = {"brightness": {"min": 30, "max": 250}, "sharpness_min_ratio": 0.5}
    data["geometry"] = {
        "fixtures": [{"name": "anchor", "locator": {"type": "blob", "version": 2, "params": {"mode": "dark", "taught_size": TAUGHT}}}],
        # the cap: the top fifth of the part, the middle half of its width
        "rois": {"cap": {"relative_to": "anchor", "rect": [0.25, 0.0, 0.75, 0.2]}},
    }
    data["tools"] = [
        {"id": "tampa", "type": "color", "version": 1, "roi": "cap", "params": {"hue": [100, 130], "s_min": 100, "min_fraction": 0.7}, "reason_fail": "Tampa ausente ({fraction:.0%} azul)"}
    ]
    data.update(changes)
    profile = CameraProfile.model_validate(yaml.safe_load((FIXTURES / "profile.yaml").read_text()))
    return JobBundle(Job.model_validate(data), profile, make_reference_files(part_scene()))


def run(bundle, image):
    return inspect_job(bundle, Frame(image, 0.0))


@pytest.mark.parametrize("angle", [-15.0, -8.0, 0.0, 5.0, 12.0, 15.0])
def test_a_part_turned_within_the_range_is_judged_like_the_straight_one(angle):
    result = run(job(), part_scene(angle))
    assert result.outcome is Outcome.PASS, (angle, result.reason)
    assert result.details["tools"]["tampa"]["fraction"] > 0.9
    (pose,) = result.fixtures
    assert pose.angle == pytest.approx(angle, abs=1.5) and pose.scale == pytest.approx(1.0, abs=0.04)


def test_without_the_pose_a_turned_part_fails_so_the_cut_is_what_makes_it_pass():
    """The control: the same picture, cut as a rectangle straight to the frame (the way it was before), misses the cap."""
    bundle = job(geometry={
        "fixtures": [{"name": "anchor", "locator": {"type": "fixed", "version": 1, "params": {"rect": [240 / W, 195 / H, 400 / W, 285 / H]}}}],
        "rois": {"cap": {"relative_to": "anchor", "rect": [0.25, 0.0, 0.75, 0.2]}},
    })
    assert run(bundle, part_scene(30.0)).outcome is Outcome.FAIL  # a fixed fixture does not turn
    wide = job().job.model_dump(mode="json")
    wide["geometry"]["fixtures"][0]["range"] = {"angle": [-40, 40], "scale": [0.9, 1.1]}
    assert run(JobBundle(Job.model_validate(wide), job().profile, job().extra), part_scene(30.0)).outcome is Outcome.PASS


def test_a_missing_cap_still_fails_on_a_turned_part():
    result = run(job(), part_scene(12.0, cap=False))
    assert result.outcome is Outcome.FAIL and result.reason.startswith("Tampa ausente")


def test_a_part_turned_more_than_the_job_allows_is_error_e202_never_fail():
    result = run(job(), part_scene(28.0))
    assert result.outcome is Outcome.ERROR and result.error_code == 202
    assert "girado" in result.reason and "15" in result.reason
    assert render(result.reason, "en").startswith("Object 'anchor' is turned")


def test_the_range_can_be_wider_or_narrower_and_the_scale_and_the_area_are_judged_too():
    wide = job()
    data = wide.job.model_dump(mode="json")
    data["geometry"]["fixtures"][0]["range"] = {"angle": [-40, 40], "scale": [0.9, 1.1]}
    assert run(JobBundle(Job.model_validate(data), wide.profile, wide.extra), part_scene(28.0)).outcome is Outcome.PASS
    data["geometry"]["fixtures"][0]["range"] = {"angle": [-15, 15], "scale": [0.9, 1.1]}
    big = run(JobBundle(Job.model_validate(data), wide.profile, wide.extra), part_scene(0.0, scale=1.3))
    assert big.outcome is Outcome.ERROR and big.error_code == 202 and "tamanho" in big.reason
    data["geometry"]["fixtures"][0]["range"] = {"angle": [-15, 15], "scale": [0.9, 1.1], "position": [0.4, 0.4, 0.6, 0.6]}
    away = run(JobBundle(Job.model_validate(data), wide.profile, wide.extra), part_scene(0.0, at=(200.0, 240.0)))
    assert away.outcome is Outcome.ERROR and away.error_code == 202 and "área" in away.reason


def test_the_result_says_where_the_part_is_and_how_it_is_turned_and_the_overlay_draws_it():
    image = part_scene(14.0)
    result = run(job(), image)
    anchor = result.details["anchor"]
    assert anchor["angle"] == pytest.approx(14.0, abs=1.5) and len(anchor["corners"]) == 4
    assert result.details["fixtures"][0]["name"] == "anchor"
    region = result.details["regions"][0]
    assert len(region["corners"]) == 4  # the cap's outline, turned
    drawn = draw_overlay(image, result)
    assert drawn.shape == image.shape and not np.array_equal(drawn, image)


def test_a_fixture_found_inside_another_follows_it_when_it_is_turned():
    """FR-INS-12: a label on a part. The label is searched in the upright cut of the part, then placed in the frame."""
    data = job().job.model_dump(mode="json")
    data["geometry"] = {
        "fixtures": [
            {"name": "part", "locator": {"type": "blob", "version": 2, "params": {"mode": "dark", "taught_size": TAUGHT}}},
            # inside the part: where the cap is, found by its colour in the part's upright picture
            {"name": "cap", "inside": "part", "locator": {"type": "blob", "version": 1, "params": {"mode": "color", "color": {"hue": [100, 130], "s_min": 100}, "min_area": 0.02}}},
        ],
        "rois": {"on_cap": {"relative_to": "cap", "rect": [0.1, 0.1, 0.9, 0.9]}},
    }
    data["tools"][0]["roi"] = "on_cap"
    bundle = job()
    bundle = JobBundle(Job.model_validate(data), bundle.profile, bundle.extra)
    for angle in (0.0, -13.0, 11.0):
        result = run(bundle, part_scene(angle))
        assert result.outcome is Outcome.PASS, (angle, result.reason)
        assert [f.name for f in result.fixtures] == ["part", "cap"]
        cap = result.fixtures[1]
        assert cap.angle == pytest.approx(angle, abs=1.5)
    assert run(bundle, part_scene(11.0, cap=False)).outcome is Outcome.ERROR  # no cap to find inside the part


def test_texts_of_a_job_are_in_both_languages_and_fall_back_to_the_other():
    data = job().job.model_dump(mode="json")
    data["tools"][0]["reason_fail"] = {"pt-BR": "Tampa ausente ({fraction:.0%} azul)", "en": "Cap missing ({fraction:.0%} blue)"}
    data["ui"] = {"waiting": {"pt-BR": "Aguardando peça", "en": ""}}
    bundle = JobBundle(Job.model_validate(data), job().profile, job().extra)
    fail = run(bundle, part_scene(0.0, cap=False))
    assert fail.outcome is Outcome.FAIL
    assert render(fail.reason, "pt-BR") == "Tampa ausente (0% azul)" and render(fail.reason, "en") == "Cap missing (0% blue)"
    waiting = bundle.job.ui.waiting
    assert waiting.get("en") == "Aguardando peça" and waiting.missing() == ["en"]  # an empty translation falls back, and says so
    assert "pt-BR" in dump_job(bundle.job) and "en:" in dump_job(bundle.job)
    assert parse_job(dump_job(bundle.job)) == bundle.job


def test_a_job_of_the_first_format_is_refused_with_a_clear_message():
    text = (FIXTURES / "job.yaml").read_text(encoding="utf-8").replace("format: 2", "format: 1")
    with pytest.raises(ValueError, match="no longer supported"):
        parse_job(text)
