import cv2
import numpy as np
import pytest
import yaml

from test_verification import FIXTURES, png
from vision_station.cameras import Frame
from vision_station.jobs import CameraProfile, Job
from vision_station.locators import LocatorError, check_job_locator, locator_types, run_locator
from vision_station.pipeline import inspect_job
from vision_station.core.results import Outcome
from vision_station.store import JobBundle
from vision_station.store.bundle import bundle_from_files
from vision_station.store.errors import FormatError
from vision_station.verification import make_reference_files

BENCH, PART, CAP = (205, 205, 200), (70, 70, 75), (200, 90, 30)  # BGR: light bench, dark part, blue cap


def part_texture(h=120, w=160):
    """A dark part with a printed pattern, so a template has something to match."""
    rng = np.random.default_rng(3)
    blocks = rng.integers(0, 2, (h // 10, w // 10), dtype=np.uint8)
    tex = np.kron(blocks, np.ones((10, 10), np.uint8))
    img = np.full((h, w, 3), PART, np.uint8)
    img[tex == 1] = (150, 150, 150)
    return img


def scene(at=(200, 150), size=(480, 640), cap=True):
    """A bench with the part at `at` (x, y of its top-left), optionally with a blue cap on top."""
    img = np.full((*size, 3), BENCH, np.uint8)
    if at is not None:
        x, y = at
        img[y : y + 120, x : x + 160] = part_texture()
        if cap:
            img[y : y + 20, x + 50 : x + 110] = CAP
    return img


def frac(rect, size=(480, 640)):
    h, w = size
    return pytest.approx((rect[0] / w, rect[1] / h, rect[2] / w, rect[3] / h), abs=2 / w)


def test_registered():
    assert {("fixed", 1), ("template", 1), ("blob", 1)} <= set(locator_types())


# --- template ----------------------------------------------------------------


def template_files(reference, box=(200, 150, 360, 270)):
    x0, y0, x1, y1 = box
    return {"locator/template.png": png(reference[y0:y1, x0:x1])}


def test_template_finds_the_part_where_it_is():
    files = template_files(scene())
    a = run_locator("template", 1, scene(at=(300, 250)), {"template": "locator/template.png"}, files)
    assert a is not None and a.score > 0.95
    assert a.rect == frac((300, 250, 460, 370))


def test_template_tolerates_light_changes_but_not_absence():
    files = template_files(scene())
    dim = (scene(at=(120, 60)).astype(np.float32) * 0.55 + 20).astype(np.uint8)
    a = run_locator("template", 1, dim, {"template": "locator/template.png"}, files)
    assert a is not None and a.rect == frac((120, 60, 280, 180))
    assert run_locator("template", 1, scene(at=None), {"template": "locator/template.png"}, files) is None


def test_template_on_a_large_frame_is_matched_smaller_and_still_placed_right():
    big = cv2.resize(scene(), (1920, 1440), interpolation=cv2.INTER_NEAREST)
    files = {"t.png": png(big[450:810, 600:1080])}
    moved = cv2.resize(scene(at=(260, 180)), (1920, 1440), interpolation=cv2.INTER_NEAREST)
    a = run_locator("template", 1, moved, {"template": "t.png"}, files)
    assert a is not None and a.rect == frac((780, 540, 1260, 900), size=(1440, 1920))


def test_template_search_area_limits_where_it_looks():
    files = template_files(scene())
    frame = scene(at=(400, 300))
    assert run_locator("template", 1, frame, {"template": "locator/template.png", "search": [0, 0, 0.5, 0.5]}, files) is None
    assert run_locator("template", 1, frame, {"template": "locator/template.png", "search": [0.5, 0.5, 1, 1]}, files) is not None


def test_template_flat_or_missing_is_an_error():
    flat = {"t.png": png(np.full((40, 40, 3), 128, np.uint8))}
    with pytest.raises(LocatorError, match="flat"):
        run_locator("template", 1, scene(), {"template": "t.png"}, flat)
    with pytest.raises(Exception, match="not in the job"):
        run_locator("template", 1, scene(), {"template": "t.png"}, {})


# --- blob --------------------------------------------------------------------


def test_blob_dark_part_on_a_light_bench():
    a = run_locator("blob", 1, scene(at=(100, 200), cap=False), {"mode": "dark", "threshold": 180})
    assert a is not None and a.rect == frac((100, 200, 260, 320))
    plain = np.full((480, 640, 3), BENCH, np.uint8)
    plain[200:320, 100:260] = PART
    a = run_locator("blob", 1, plain, {"mode": "dark"})  # automatic threshold, for an even part
    assert a is not None and a.rect == frac((100, 200, 260, 320)) and a.score == pytest.approx(1.0, abs=0.01)


def test_blob_by_color_finds_the_cap():
    a = run_locator("blob", 1, scene(at=(100, 200)), {"mode": "color", "color": {"hue": [100, 130], "s_min": 100}, "min_area": 0.001})
    assert a is not None and a.rect == frac((150, 200, 210, 220))


def test_blob_ignores_regions_outside_the_size_limits_and_the_search_area():
    img = scene(at=None)
    img[10:14, 10:14] = PART  # a speck
    assert run_locator("blob", 1, img, {"mode": "dark", "threshold": 120}) is None
    img = scene(at=(400, 300), cap=False)
    assert run_locator("blob", 1, img, {"mode": "dark", "search": [0, 0, 0.5, 0.5]}) is None


def test_blob_light_mode_and_invalid_parameters():
    img = np.full((100, 100, 3), 30, np.uint8)
    img[20:60, 30:80] = 240
    a = run_locator("blob", 1, img, {"mode": "light"})
    assert a is not None and a.rect == frac((30, 20, 80, 60), size=(100, 100))
    with pytest.raises(LocatorError):
        run_locator("blob", 1, img, {"mode": "color"})  # needs a color
    with pytest.raises(LocatorError):
        run_locator("blob", 1, img, {"mode": "dark", "min_area": 0.5, "max_area": 0.1})


@pytest.mark.parametrize("seed", range(10))
def test_locators_never_crash_on_noise(seed):
    rng = np.random.default_rng(seed)
    img = rng.integers(0, 256, (90, 120, 3), dtype=np.uint8)
    files = template_files(scene())
    run_locator("blob", 1, img, {"mode": "dark"})
    run_locator("template", 1, img, {"template": "locator/template.png"}, files)


# --- in a job ----------------------------------------------------------------


def job_with_template_locator(reference):
    data = yaml.safe_load((FIXTURES / "job.yaml").read_text(encoding="utf-8"))
    data["quality"] = {"brightness": {"min": 30, "max": 250}, "sharpness_min_ratio": 0.5}
    data["geometry"] = {
        "locator": {"type": "template", "version": 1, "params": {"template": "locator/template.png"}},
        "rois": {"cap": {"relative_to": "anchor", "rect": [0.25, 0.0, 0.75, 0.25]}},
    }
    data["tools"] = [
        {"id": "tampa", "type": "color", "version": 1, "roi": "cap", "params": {"hue": [100, 130], "s_min": 100, "min_fraction": 0.4}, "reason_fail": "Tampa ausente ({fraction:.0%} azul)"}
    ]
    profile = CameraProfile.model_validate(yaml.safe_load((FIXTURES / "profile.yaml").read_text()))
    return JobBundle(Job.model_validate(data), profile, {**make_reference_files(reference), **template_files(reference)})


def test_regions_follow_the_part_and_the_tool_judges_the_cap():
    bundle = job_with_template_locator(scene())
    moved = inspect_job(bundle, Frame(scene(at=(380, 40)), 0.0))
    assert moved.outcome is Outcome.PASS, moved.reason
    x0, y0, x1, y1 = moved.details["regions"][0]["rect"]
    assert abs(x0 - 420) <= 2 and abs(y0 - 40) <= 2 and abs(x1 - 500) <= 2 and abs(y1 - 70) <= 2

    no_cap = inspect_job(bundle, Frame(scene(at=(380, 40), cap=False), 0.0))
    assert no_cap.outcome is Outcome.FAIL and no_cap.reason == "Tampa ausente (0% azul)"

    gone = inspect_job(bundle, Frame(scene(at=None), 0.0))
    # a plain bench is also "not sharp": the reason says both, never a pass
    assert gone.outcome is Outcome.ERROR and gone.reason.startswith("Objeto não encontrado")
    noisy_bench = np.clip(scene(at=None).astype(np.int16) + np.random.default_rng(0).integers(-40, 40, (480, 640, 1)), 0, 255).astype(np.uint8)
    assert inspect_job(bundle, Frame(noisy_bench, 0.0)).reason == "Objeto não encontrado na posição esperada"

    blurred = cv2.GaussianBlur(scene(at=(380, 40)), (0, 0), 6)
    r = inspect_job(bundle, Frame(blurred, 0.0))
    assert r.outcome is Outcome.ERROR and "foco" in r.reason


def test_a_job_whose_template_is_missing_is_refused_when_loaded():
    bundle = job_with_template_locator(scene())
    with pytest.raises(LocatorError, match="missing files"):
        check_job_locator(bundle.job, {})
    files = {k: v for k, v in bundle.files().items() if k != "locator/template.png"}
    with pytest.raises(FormatError, match="locator/template.png"):
        bundle_from_files(files)
    assert bundle_from_files(bundle.files()).job == bundle.job


# --- blob v2: a pose (architecture §14, FR-INS-11) ---------------------------------------------------------


def turned_part(angle, size=(480, 640), at=(320.0, 240.0), scale=1.0):
    """A dark 160 x 90 part on a light bench, turned counter-clockwise on the screen by `angle` degrees."""
    img = np.full((*size, 3), BENCH, np.uint8)
    cx, cy = at
    img[round(cy - 45) : round(cy + 45), round(cx - 80) : round(cx + 80)] = PART
    matrix = cv2.getRotationMatrix2D(at, angle, scale)
    return cv2.warpAffine(img, matrix, (size[1], size[0]), flags=cv2.INTER_LINEAR, borderValue=BENCH)


def test_blob_v2_is_registered_next_to_v1():
    assert {("blob", 1), ("blob", 2)} <= set(locator_types())


@pytest.mark.parametrize("angle", [-15.0, -6.0, 0.0, 8.0, 15.0, 30.0])
def test_blob_v2_gives_the_centre_and_the_angle_of_a_turned_part(angle):
    a = run_locator("blob", 2, turned_part(angle), {"mode": "dark", "taught_size": [160, 90]})
    assert a is not None
    assert a.angle == pytest.approx(angle, abs=1.5)
    cx, cy = a.centre
    assert (cx * 640, cy * 480) == pytest.approx((320, 240), abs=2.0)
    assert a.scale == pytest.approx(1.0, abs=0.03)
    assert a.score > 0.9


def test_blob_v2_with_the_taught_size_tells_the_long_side_from_the_short_one():
    """A part turned past 45° is the same rectangle as one turned the other way: the taught proportions decide."""
    a = run_locator("blob", 2, turned_part(70.0), {"mode": "dark", "taught_size": [160, 90]})
    assert a is not None and a.angle == pytest.approx(70.0, abs=2.0)
    b = run_locator("blob", 2, turned_part(-70.0), {"mode": "dark", "taught_size": [160, 90]})
    assert b is not None and b.angle == pytest.approx(-70.0, abs=2.0)
    portrait = run_locator("blob", 2, turned_part(0.0), {"mode": "dark", "taught_size": [90, 160]})  # taught standing up
    assert portrait is not None and abs(portrait.angle) == pytest.approx(90.0, abs=2.0)


def test_blob_v2_without_a_taught_size_gives_the_smallest_turn_and_the_size_found():
    a = run_locator("blob", 2, turned_part(20.0), {"mode": "dark"})
    assert a is not None and a.angle == pytest.approx(20.0, abs=2.0) and a.scale == 1.0
    x0, y0, x1, y1 = a.rect
    assert ((x1 - x0) * 640, (y1 - y0) * 480) == pytest.approx((160, 90), abs=3)


def test_blob_v2_measures_the_scale():
    a = run_locator("blob", 2, turned_part(10.0, scale=1.3), {"mode": "dark", "taught_size": [160, 90]})
    assert a is not None and a.scale == pytest.approx(1.3, abs=0.04)


def test_blob_v2_finds_nothing_where_there_is_nothing_and_v1_is_unchanged():
    plain = np.full((480, 640, 3), BENCH, np.uint8)
    assert run_locator("blob", 2, plain, {"mode": "dark"}) is None
    a = run_locator("blob", 1, turned_part(0.0), {"mode": "dark"})
    assert a is not None and a.angle == 0.0 and a.scale == 1.0  # the upright rectangle, as always
