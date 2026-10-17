import cv2
import numpy as np
import pytest

from test_verification import make_bundle, no_code_scene, qr_scene
from vision_station.cameras import Frame
from vision_station.jobs import Job
from vision_station.locators import LocatorError, check_job_locator, locator_types, run_locator
from vision_station.pipeline import draw_overlay, inspect_job
from vision_station.core.results import Outcome
from vision_station.store import JobBundle
from vision_station.tools import ToolType, register
from vision_station.tools.base import ToolResult
from vision_station.verification import verify_job
from pydantic import BaseModel


def frame(img):
    return Frame(img, 0.0)


def with_job(bundle, **changes):
    data = bundle.job.model_dump(mode="json")
    data.update(changes)
    return JobBundle(Job.model_validate(data), bundle.profile, bundle.extra)


def test_pass_and_fail_with_the_code_tool():
    bundle = make_bundle()
    ok = inspect_job(bundle, frame(qr_scene("LOTE-1")))
    assert ok.outcome is Outcome.PASS and ok.scores["lote"] == 1.0
    bad = inspect_job(bundle, frame(no_code_scene()))
    assert bad.outcome is Outcome.FAIL and bad.reason == "Código não lido"
    assert {"quality", "locate", "tools", "total", "per_tool"} <= set(ok.details["timings"])
    assert ok.duration_s == ok.details["timings"]["total"]
    assert ok.details["regions"][0]["rect"] == [0, 0, 320, 240]


def test_verification_accepts_the_pipeline():
    assert verify_job(make_bundle(), inspect=inspect_job, parts="decision").ok


def test_quality_gate():
    bundle = make_bundle(brightness=(50, 200))
    dark = inspect_job(bundle, frame((qr_scene("LOTE-1") * 0.1).astype(np.uint8)))
    assert dark.outcome is Outcome.ERROR and "escura" in dark.reason
    bright = inspect_job(bundle, frame(qr_scene("LOTE-1")))  # mostly white
    assert bright.outcome is Outcome.ERROR and "clara demais" in bright.reason
    blank = inspect_job(make_bundle(), frame(np.full((240, 320, 3), 255, np.uint8)))
    assert blank.outcome is Outcome.ERROR  # a flat picture is a lens cap or a dead camera, never a FAIL
    blurred = inspect_job(make_bundle(), frame(cv2.GaussianBlur(qr_scene("LOTE-1"), (31, 31), 10)))
    assert blurred.outcome is Outcome.ERROR and "foco" in blurred.reason


def test_roi_crops_and_second_tool_failure_listed():
    bundle = make_bundle()
    img = np.full((240, 640, 3), 255, np.uint8)
    img[:, :320] = qr_scene("LOTE-1")
    job = bundle.job.model_dump(mode="json")
    job["geometry"] = {"rois": {"left": {"relative_to": "frame", "rect": [0, 0, 0.5, 1]}, "right": {"relative_to": "frame", "rect": [0.5, 0, 1, 1]}}}
    job["tools"] = [
        {"id": "a", "type": "code", "version": 1, "roi": "left", "reason_fail": "A falhou"},
        {"id": "b", "type": "code", "version": 1, "roi": "right", "reason_fail": "B falhou"},
    ]
    b = JobBundle(Job.model_validate(job), bundle.profile, {})
    result = inspect_job(b, frame(img))
    assert result.outcome is Outcome.FAIL and result.reason == "B falhou"
    assert [r["passed"] for r in result.details["regions"]] == [True, False]
    assert result.details["regions"][1]["rect"] == [320, 0, 640, 240]


def test_fixed_locator_and_anchor_relative_roi():
    assert ("fixed", 1) in locator_types()
    bundle = make_bundle()
    img = np.full((240, 640, 3), 255, np.uint8)
    img[:, 320:] = qr_scene("LOTE-1")
    job = bundle.job.model_dump(mode="json")
    job["geometry"] = {"locator": {"type": "fixed", "version": 1, "params": {"rect": [0.5, 0, 1, 1]}},
                       "rois": {"label": {"relative_to": "anchor", "rect": [0, 0, 1, 1]}}}
    b = JobBundle(Job.model_validate(job), bundle.profile, {})
    result = inspect_job(b, frame(img))
    assert result.outcome is Outcome.PASS and result.details["anchor"]["rect"] == [0.5, 0, 1, 1]
    assert result.details["regions"][0]["rect"] == [320, 0, 640, 240]
    out = draw_overlay(img, result)
    assert out.shape == img.shape and not np.array_equal(out, img)


def test_locator_validation_and_not_found():
    with pytest.raises(LocatorError):
        run_locator("fixed", 1, np.zeros((4, 4, 3), np.uint8), {"rect": [0.6, 0, 0.5, 1]})
    with pytest.raises(LocatorError):
        run_locator("nope", 1, np.zeros((4, 4, 3), np.uint8), {})
    bundle = make_bundle()
    job = bundle.job.model_dump(mode="json")
    job["geometry"]["locator"] = {"type": "fixed", "version": 9, "params": {}}
    with pytest.raises(LocatorError):
        check_job_locator(Job.model_validate(job))
    r = inspect_job(JobBundle(Job.model_validate(job), bundle.profile, {}), frame(qr_scene("LOTE-1")))
    assert r.outcome is Outcome.ERROR


def test_broken_tool_and_bad_score_are_errors():
    class P(BaseModel):
        pass

    def boom(region, params, files):
        raise RuntimeError("x")

    register(ToolType("test_boom", 1, P, boom))
    register(ToolType("test_nan", 1, P, lambda r, p, f: ToolResult(True, float("nan"))))
    bundle = make_bundle()
    for name in ("test_boom", "test_nan"):
        job = bundle.job.model_dump(mode="json")
        job["tools"] = [{"id": "t", "type": name, "version": 1, "roi": "frame", "reason_fail": "x"}]
        r = inspect_job(JobBundle(Job.model_validate(job), bundle.profile, {}), frame(qr_scene("LOTE-1")))
        assert r.outcome is Outcome.ERROR


def test_unknown_tool_version_is_error():
    bundle = make_bundle()
    job = bundle.job.model_dump(mode="json")
    job["tools"][0]["version"] = 99
    r = inspect_job(JobBundle(Job.model_validate(job), bundle.profile, {}), frame(qr_scene("LOTE-1")))
    assert r.outcome is Outcome.ERROR and "não pode rodar" in r.reason


def test_region_outside_is_error():
    bundle = make_bundle()
    job = bundle.job.model_dump(mode="json")
    job["geometry"]["rois"]["label"]["rect"] = [0.5, 0.5, 0.5001, 0.5001]
    r = inspect_job(JobBundle(Job.model_validate(job), bundle.profile, {}), frame(np.full((10, 10, 3), 255, np.uint8)))
    assert r.outcome is Outcome.ERROR and "fora da imagem" in r.reason


def test_a_region_on_the_anchor_without_an_anchor_is_an_error_with_its_reason():
    # job validation already refuses both; the pipeline checks again and keeps its own reason
    bundle = make_bundle()
    roi = bundle.job.geometry.rois["label"]
    on_anchor = bundle.job.geometry.model_copy(update={"rois": {"label": roi.model_copy(update={"relative_to": "anchor"})}})
    job = bundle.job.model_copy(update={"geometry": on_anchor})
    r = inspect_job(JobBundle(job, bundle.profile, {}), frame(qr_scene("LOTE-1")))
    assert r.outcome is Outcome.ERROR and r.reason == "Região 'label' depende do objeto, que não foi localizado"
    tool = bundle.job.tools[0].model_copy(update={"roi": "anchor"})
    job = bundle.job.model_copy(update={"tools": [tool]})
    r = inspect_job(JobBundle(job, bundle.profile, {}), frame(qr_scene("LOTE-1")))
    assert r.outcome is Outcome.ERROR and r.reason == "Região 'anchor' sem localizador"


@pytest.mark.parametrize("seed", range(20))
def test_garbage_frames_never_pass_or_raise(seed):
    rng = np.random.default_rng(seed)
    bundle = make_bundle()
    shapes = [(1, 1, 3), (240, 320), (50, 50, 3), (0, 5, 3)]
    img = rng.integers(0, 256, shapes[seed % 4], dtype=np.uint8)
    assert inspect_job(bundle, frame(img)).outcome is not Outcome.PASS
    assert inspect_job(bundle, frame(None)).outcome is Outcome.ERROR
