from pathlib import Path

import cv2
import numpy as np
import pytest
import yaml
import zxingcpp

from test_station import Rig, State, empty_scene, make_bundle as station_bundle
from vision_station.cameras import ApplyReport, Frame, SettingStatus
from vision_station.jobs import CameraProfile, Job
from vision_station.core.results import InspectionResult, Outcome
from vision_station.station import Acquisition
from vision_station.store import JobBundle, JobRef, JobStore
from vision_station.tools import run_tool
from vision_station.verification import (
    EXPECTED_FILE,
    JobVerifier,
    VerificationFailed,
    activate,
    make_reference_files,
    parse_expected,
    verify_job,
    verify_live,
    verify_stored_job,
)
from vision_station.algorithms import metrics

FIXTURES = Path(__file__).parent / "fixtures"
JOB_ID = "3f1c9a2e-5b7d-4c1e-9a0f-2d6b8e4f7a10"


def qr_scene(text, size=(240, 320)):
    gray = np.array(zxingcpp.create_barcode(text, zxingcpp.BarcodeFormat.QRCode).to_image(scale=4))
    canvas = np.full(size, 255, np.uint8)
    y, x = (size[0] - gray.shape[0]) // 2, (size[1] - gray.shape[1]) // 2
    canvas[y : y + gray.shape[0], x : x + gray.shape[1]] = gray
    return cv2.cvtColor(canvas, cv2.COLOR_GRAY2BGR)


def no_code_scene(size=(240, 320)):
    """A picture as sharp as a code but with none in it: random black and white blocks."""
    blocks = np.random.default_rng(7).integers(0, 2, (size[0] // 8 - 8, size[1] // 8 - 8), dtype=np.uint8) * 255
    gray = np.full(size, 255, np.uint8)
    gray[32:-32, 32:-32] = np.kron(blocks, np.ones((8, 8), np.uint8))
    return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)


def png(image):
    return cv2.imencode(".png", image)[1].tobytes()


def inspect_code(bundle, frame):
    """A real inspection: PASS when the code tool reads a code."""
    r = run_tool("code", 1, frame.image, {})
    return InspectionResult(Outcome.PASS if r.passed else Outcome.FAIL, "" if r.passed else "Código não lido", scores={"lote": r.score})


def expected_yaml(cases, tolerance=0.05):
    return yaml.safe_dump({"tolerance": tolerance, "cases": cases}, sort_keys=False).encode()


def make_bundle(brightness=(0, 255), extra=None, **quality) -> JobBundle:
    data = yaml.safe_load((FIXTURES / "job.yaml").read_text(encoding="utf-8"))
    data["job"].update(id=JOB_ID, name="Etiqueta de lote", version=1, parent_version=None)
    data["geometry"] = {"rois": {"label": {"relative_to": "frame", "rect": [0, 0, 1, 1]}}}
    data["tools"] = [{"id": "lote", "type": "code", "version": 1, "roi": "label", "reason_fail": "Código não lido"}]
    data["quality"] = {"brightness": {"min": brightness[0], "max": brightness[1]}, "sharpness_min_ratio": 0.5, **quality}
    reference = qr_scene("LOTE-1")
    files = {
        **make_reference_files(reference),
        "tests/images/ok1.png": png(qr_scene("LOTE-1")),
        "tests/images/ok2.png": png(qr_scene("LOTE-2")),
        "tests/images/blank.png": png(no_code_scene()),
        EXPECTED_FILE: expected_yaml(
            [
                {"image": "tests/images/ok1.png", "outcome": "PASS", "scores": {"lote": 1.0}},
                {"image": "tests/images/ok2.png", "outcome": "PASS"},
                {"image": "tests/images/blank.png", "outcome": "FAIL", "reason_contains": "não lido"},
            ]
        ),
    }
    profile = CameraProfile.model_validate(yaml.safe_load((FIXTURES / "profile.yaml").read_text()))
    return JobBundle(Job.model_validate(data), profile, extra=files if extra is None else extra)


OK_APPLY = ApplyReport(status={"exposure": SettingStatus.APPLIED})
GOOD_FRAME = Frame(qr_scene("LOTE-1"), 1.0)


def names(checks):
    return {c.name: c.passed for c in checks}


# --- measures ----------------------------------------------------------------


def test_measures_respond_to_brightness_blur_and_a_different_scene():
    img = qr_scene("A-1")
    assert metrics.brightness(img) == pytest.approx(img.mean(), abs=1)
    blurred = cv2.GaussianBlur(img, (21, 21), 6)
    assert metrics.sharpness(blurred) < 0.2 * metrics.sharpness(img)
    assert metrics.sharpness(cv2.resize(img, (640, 480))) > 0  # any resolution
    assert metrics.similarity(img, img) == pytest.approx(1.0)
    assert metrics.similarity(img, (img * 0.5).astype(np.uint8)) > 0.95  # overall brightness alone does not matter
    shifted = np.roll(img, 3, axis=1)
    assert metrics.similarity(img, shifted) > 0.8  # a small shift is tolerated
    assert metrics.similarity(img, qr_scene("OTHER-TEXT-LONGER-0123456789")) < 0.9
    noise = np.random.default_rng(0).integers(0, 255, img.shape, dtype=np.uint8)
    assert metrics.similarity(img, noise) < 0.3
    flat = np.full_like(img, 120)
    assert metrics.similarity(flat, flat) == 1.0 and metrics.similarity(flat, img) == 0.0


# --- camera and view ---------------------------------------------------------


def test_a_good_view_passes_every_camera_check():
    report = verify_job(make_bundle(), inspect=inspect_code, apply_report=OK_APPLY, frame=GOOD_FRAME, parts="camera")
    assert report.ok, report.failures()
    assert set(names(report.camera_view)) == {"settings", "frame", "brightness", "sharpness", "similarity"}
    assert report.summary() == "Job verificado"


def test_settings_the_camera_refused_fail_and_unsupported_ones_are_warnings():
    refused = ApplyReport(status={"exposure": SettingStatus.REJECTED, "zoom": SettingStatus.NOT_SUPPORTED}, detail={"exposure": "kept auto", "zoom": "no zoom"})
    report = verify_job(make_bundle(), inspect=inspect_code, apply_report=refused, frame=GOOD_FRAME, parts="camera")
    assert not report.ok and "exposure: kept auto" in report.summary()
    assert any("zoom" in w for w in report.warnings)
    assert not verify_job(make_bundle(), inspect=inspect_code, apply_report=None, frame=GOOD_FRAME, parts="camera").ok


def test_no_frame_fails():
    report = verify_job(make_bundle(), inspect=inspect_code, apply_report=OK_APPLY, frame=None, parts="camera")
    assert not report.ok and "sem imagem" in report.summary()


def test_too_dark_or_too_bright_fails_against_the_job_limits():
    bundle = make_bundle(brightness=(90, 170))  # the white label scene is about 235
    report = verify_job(bundle, inspect=inspect_code, apply_report=OK_APPLY, frame=GOOD_FRAME, parts="camera")
    assert not names(report.camera_view)["brightness"] and "brilho" in report.summary()
    dark = Frame((GOOD_FRAME.image * 0.3).astype(np.uint8), 2.0)
    assert not verify_job(make_bundle(brightness=(150, 255)), inspect=inspect_code, apply_report=OK_APPLY, frame=dark, parts="camera").ok


def test_out_of_focus_is_caught_by_sharpness():
    blurred = Frame(cv2.GaussianBlur(GOOD_FRAME.image, (15, 15), 4), 2.0)
    report = verify_job(make_bundle(), inspect=inspect_code, apply_report=OK_APPLY, frame=blurred, parts="camera")
    assert not names(report.camera_view)["sharpness"] and "foco" in report.summary()


def test_a_moved_camera_or_other_scene_is_caught_by_similarity():
    other = Frame(np.random.default_rng(3).integers(0, 255, GOOD_FRAME.image.shape, dtype=np.uint8), 2.0)
    report = verify_job(make_bundle(), inspect=inspect_code, apply_report=OK_APPLY, frame=other, parts="camera")
    assert not names(report.camera_view)["similarity"] and "câmera movida" in report.summary()


def test_anchor_position_is_checked_when_a_locator_is_given():
    bundle = make_bundle()
    ref = qr_scene("LOTE-1")
    files = make_reference_files(ref, locate=lambda img: (0.50, 0.50))
    bundle = JobBundle(bundle.job, bundle.profile, extra={**bundle.extra, **files})
    near = verify_job(bundle, inspect=inspect_code, apply_report=OK_APPLY, frame=GOOD_FRAME, parts="camera", locate=lambda img: (0.52, 0.49))
    assert near.ok and "anchor" in names(near.camera_view)
    far = verify_job(bundle, inspect=inspect_code, apply_report=OK_APPLY, frame=GOOD_FRAME, parts="camera", locate=lambda img: (0.60, 0.50))
    assert not far.ok and "deslocada" in far.summary()
    lost = verify_job(bundle, inspect=inspect_code, apply_report=OK_APPLY, frame=GOOD_FRAME, parts="camera", locate=lambda img: None)
    assert not lost.ok and "não encontrado" in lost.summary()


def test_a_job_without_reference_image_warns_instead_of_failing():
    bundle = make_bundle(extra={})
    report = verify_job(bundle, inspect=inspect_code, apply_report=OK_APPLY, frame=GOOD_FRAME)
    assert report.ok
    assert any("imagem de referência" in w for w in report.warnings) and any("conjunto de referência" in w for w in report.warnings)
    assert not verify_job(bundle, inspect=inspect_code, apply_report=OK_APPLY, frame=GOOD_FRAME, require_reference_set=True).ok


# --- decision logic ----------------------------------------------------------


def test_the_reference_set_gives_the_expected_results():
    report = verify_job(make_bundle(), inspect=inspect_code, parts="decision")
    assert report.ok, report.failures()
    assert len(report.decision) == 3 and not report.camera_view


def test_a_wrong_outcome_or_score_or_reason_fails_the_case():
    bundle = make_bundle()
    always_pass = lambda b, f: InspectionResult(Outcome.PASS, scores={"lote": 1.0})
    report = verify_job(bundle, inspect=always_pass, parts="decision")
    assert not report.ok and "resultado PASS, esperado FAIL" in report.summary()
    wrong_score = lambda b, f: InspectionResult(Outcome.PASS if run_tool("code", 1, f.image, {}).passed else Outcome.FAIL, "Código não lido", scores={"lote": 0.5})
    report = verify_job(bundle, inspect=wrong_score, parts="decision")
    assert "nota de 'lote' 0.500, esperada 1.000" in report.summary()
    wrong_reason = lambda b, f: InspectionResult(Outcome.PASS if f.image.min() < 255 else Outcome.FAIL, "outra coisa", scores={"lote": 1.0})
    assert "não contém 'não lido'" in verify_job(bundle, inspect=wrong_reason, parts="decision").summary()
    no_scores = lambda b, f: InspectionResult(Outcome.PASS if run_tool("code", 1, f.image, {}).passed else Outcome.FAIL, "Código não lido")
    assert "nota de 'lote' ausente" in verify_job(bundle, inspect=no_scores, parts="decision").summary()


def test_the_tolerance_on_scores_is_respected():
    bundle = make_bundle()
    slightly_off = lambda b, f: InspectionResult(Outcome.PASS if run_tool("code", 1, f.image, {}).passed else Outcome.FAIL, "Código não lido", scores={"lote": 0.97})
    assert verify_job(bundle, inspect=slightly_off, parts="decision").ok  # 0.03 < 0.05


def test_a_missing_image_or_a_crashing_inspection_fails_the_case_without_crashing():
    bundle = make_bundle()
    extra = {k: v for k, v in bundle.extra.items() if k != "tests/images/ok2.png"}
    report = verify_job(JobBundle(bundle.job, bundle.profile, extra=extra), inspect=inspect_code, parts="decision")
    assert not report.ok and "ausente" in report.summary()

    def crash(b, f):
        raise RuntimeError("model file corrupt")

    report = verify_job(bundle, inspect=crash, parts="decision")
    assert not report.ok and "model file corrupt" in report.summary() and len(report.failures()) == 3


def test_expected_file_must_be_valid():
    from vision_station.store import FormatError

    with pytest.raises(FormatError):
        parse_expected(b"cases: []\n")
    with pytest.raises(FormatError):
        parse_expected(b"cases: [{image: a.png, outcome: MAYBE}]\n")
    assert parse_expected(expected_yaml([{"image": "a.png", "outcome": "PASS"}])).tolerance == 0.05


# --- activation --------------------------------------------------------------


@pytest.fixture
def store(tmp_path):
    return JobStore(tmp_path / "data")


def test_activation_needs_a_passing_report_or_a_recorded_override(store):
    ref = store.save(make_bundle())
    good = verify_job(make_bundle(), inspect=inspect_code, apply_report=OK_APPLY, frame=GOOD_FRAME)
    bad = verify_job(make_bundle(), inspect=inspect_code, apply_report=OK_APPLY, frame=None)
    with pytest.raises(VerificationFailed, match="sem imagem"):
        activate(store, ref, bad)
    with pytest.raises(VerificationFailed):
        activate(store, ref, bad, override_reason="   ")
    assert store.get_active() is None
    activate(store, ref, good)
    assert store.get_active() == ref
    store.set_active(ref)
    activate(store, ref, bad, override_reason="câmera em manutenção, conferido a olho")
    kinds = [e["kind"] for e in store.read_audit()]
    assert kinds == ["activate", "activate_override"]
    override = store.read_audit()[-1]
    assert override["reason"].startswith("câmera em manutenção") and "sem imagem" in override["failures"][0]


# --- with the live camera and the station ------------------------------------


def test_verify_live_applies_the_job_settings_and_runs_both_parts(store):
    ref = store.save(make_bundle())
    rig = Rig()
    rig.camera.scene = qr_scene("LOTE-1")
    report = verify_live(store, ref, rig.acq, inspect_code, drive_acquisition=True, clock=rig.clock, sleep=lambda s: rig.clock.advance(0.05))
    assert report.ok, report.failures()
    assert len(report.decision) == 3 and len(rig.camera.applied) == 1


def test_verify_live_reports_a_camera_that_never_answers(store):
    ref = store.save(make_bundle())
    rig = Rig()
    rig.camera.fail_open = True
    report = verify_live(store, ref, rig.acq, inspect_code, drive_acquisition=True, timeout_s=2.0, clock=rig.clock, sleep=lambda s: rig.clock.advance(0.25))
    assert not report.ok and "não respondeu" in report.summary()


def test_the_station_uses_the_full_verification():
    def rig_with(scene):
        rig = Rig()
        rig.camera.scene = scene
        bundle = station_bundle()
        extra = make_reference_files(empty_scene())
        rig.bundle = JobBundle(bundle.job, bundle.profile, extra=extra)
        rig.verifier = JobVerifier(lambda b, f: InspectionResult(Outcome.PASS))
        rig.controller._verify = rig.verifier
        return rig

    good = rig_with(empty_scene())
    good.controller.start(good.bundle)
    good.tick(4)
    assert good.state is State.READY and good.verifier.last_report.ok

    wrong = rig_with(np.random.default_rng(5).integers(0, 255, empty_scene().shape, dtype=np.uint8))
    wrong.bundle = JobBundle(wrong.bundle.job.model_copy(update={"quality": wrong.bundle.job.quality.model_copy(update={"brightness": wrong.bundle.job.quality.brightness})}), wrong.bundle.profile, extra=wrong.bundle.extra)
    wrong.controller.start(wrong.bundle)
    wrong.tick(4)
    assert wrong.state is State.FAULT
    assert "imagem diferente da referência" in wrong.controller.status().detail


# --- restore gives the same results (NFR-REL-5) -------------------------------


def test_a_restored_job_gives_the_same_results_on_its_reference_set(store, tmp_path):
    ref = store.save(make_bundle())
    store.set_active(ref)
    assert verify_stored_job(store, ref, inspect_code).ok

    backup = store.make_backup(tmp_path / "usb")
    fresh = JobStore(tmp_path / "new-pc")
    restored = fresh.restore_backup(backup.read_bytes())
    new_ref = restored.active
    assert new_ref == ref
    report = verify_stored_job(fresh, new_ref, inspect_code)
    assert report.ok, report.failures()
    # same results, case by case, not just "ok"
    original = {c.name: c.message for c in verify_stored_job(store, ref, inspect_code).decision}
    again = {c.name: c.message for c in report.decision}
    assert original == again
    activate(fresh, new_ref, report)
    assert fresh.get_active() == ref
    assert [e["kind"] for e in fresh.read_audit()] == ["import", "activate"]


def test_a_restored_job_that_behaves_differently_is_not_activated(store, tmp_path):
    ref = store.save(make_bundle())
    fresh = JobStore(tmp_path / "new-pc")
    fresh.import_vjob(store.export_vjob(ref))
    different_software = lambda b, f: InspectionResult(Outcome.PASS, scores={"lote": 1.0})  # e.g. a tool changed
    report = verify_stored_job(fresh, ref, different_software)
    assert not report.ok
    with pytest.raises(VerificationFailed):
        activate(fresh, ref, report)
    assert fresh.get_active() is None
