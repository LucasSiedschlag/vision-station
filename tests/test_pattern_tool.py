import cv2
import numpy as np
import pytest
import yaml

from test_verification import FIXTURES, png
from vision_station.jobs import Job
from vision_station.tools import ToolError, check_job_tools, run_tool, tool_types
from vision_station.tools.measures import at_least, at_most, longest_run, strip_profile

BACK = 225  # a light film over cardboard


def logo():
    """A printed mark: text and a bar, dark on light."""
    img = np.full((30, 70), BACK, np.uint8)
    cv2.putText(img, "VS-9", (4, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.7, 40, 2)
    img[26:29, 4:66] = 40
    return img


FILES = {"patterns/logo.png": png(logo())}


def strip(at_x, length=600, height=50):
    """A strip with the mark printed at each x in `at_x`."""
    img = np.full((height, length), BACK, np.uint8)
    mark = logo()
    for x in at_x:
        img[10:40, x : x + 70] = mark
    return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)


def pattern(region, **params):
    return run_tool("pattern", 1, region, {"template": "patterns/logo.png", **params}, FILES)


def test_registered():
    assert ("pattern", 1) in tool_types()


def test_finds_and_counts_each_mark_once():
    r = pattern(strip(range(0, 600, 75)))
    assert r.passed and r.values["count"] == 8 and r.values["best"] > 0.95
    assert [m["rect"][0] for m in sorted(r.details["matches"], key=lambda m: m["rect"][0])] == list(range(0, 600, 75))
    assert not pattern(strip([])).passed and pattern(strip([])).values["count"] == 0


def test_min_and_max_count():
    region = strip([0, 100, 200])
    assert pattern(region, min_count=3).passed
    r = pattern(region, min_count=4)
    assert not r.passed and r.score == pytest.approx(0.75)
    assert r.reason("{count} de {min_count} marcas") == "3 de 4 marcas"
    assert not pattern(region, max_count=2).passed  # e.g. a label applied twice
    assert pattern(strip([]), min_count=0, max_count=0).passed  # "the mark must not be there"


def test_a_missing_stretch_is_the_longest_gap_ends_included():
    full = range(0, 700, 70)  # marks touch: the whole length is covered
    r = pattern(strip(full, length=700), axis="x", min_coverage=0.9, max_gap=0.1)
    assert r.passed and r.values["coverage"] == pytest.approx(1.0)
    short = [x for x in full if x < 420]  # the print stops at 420 px: 280 px (40%) at the end without it
    r = pattern(strip(short, length=700), axis="x", min_coverage=0.9, max_gap=0.1)
    assert not r.passed and r.values["gap"] == pytest.approx(0.4) and r.details["gap_at"] == pytest.approx([0.6, 1.0])
    assert r.reason("Marca ausente em {missing:.0%} da faixa") == "Marca ausente em 40% da faixa"
    middle = [x for x in full if not 140 <= x < 350]
    assert pattern(strip(middle, length=700), axis="x", max_gap=0.1).details["gap_at"] == pytest.approx([0.2, 0.5])


def test_vertical_strip():
    region = np.ascontiguousarray(np.rot90(strip(range(0, 350, 70), length=350, height=70)))
    vertical = cv2.rotate(logo(), cv2.ROTATE_90_COUNTERCLOCKWISE)
    r = run_tool("pattern", 1, region, {"template": "v.png", "axis": "y", "min_coverage": 0.9}, {"v.png": png(vertical)})
    assert r.values["count"] == 5 and r.passed


def test_light_changes_do_not_matter_but_another_mark_does():
    dim = (strip(range(0, 600, 75)).astype(np.float32) * 0.5 + 30).astype(np.uint8)
    assert pattern(dim).values["count"] == 8
    other = np.full((50, 600), BACK, np.uint8)
    for x in range(0, 600, 75):
        cv2.putText(other, "AB", (x + 4, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.9, 40, 2)
    assert pattern(cv2.cvtColor(other, cv2.COLOR_GRAY2BGR)).values["count"] == 0


def test_a_large_region_is_matched_smaller_and_reported_in_region_pixels():
    big = cv2.resize(strip([0, 300]), None, fx=3, fy=3, interpolation=cv2.INTER_NEAREST)  # 1800 px long
    files = {"big.png": png(cv2.resize(logo(), None, fx=3, fy=3, interpolation=cv2.INTER_NEAREST))}
    r = run_tool("pattern", 1, big, {"template": "big.png", "min_count": 2}, files)
    assert r.passed
    xs = sorted(m["rect"][0] for m in r.details["matches"])
    assert xs[0] == pytest.approx(0, abs=3) and xs[1] == pytest.approx(900, abs=3)


def test_template_problems_are_errors_not_fails():
    with pytest.raises(ToolError, match="larger than the region"):
        pattern(strip([0])[:20, :50])
    with pytest.raises(ToolError, match="flat"):
        run_tool("pattern", 1, strip([0]), {"template": "f.png"}, {"f.png": png(np.full((10, 10), 9, np.uint8))})
    with pytest.raises(Exception, match="not in the job"):
        run_tool("pattern", 1, strip([0]), {"template": "nope.png"}, {})
    with pytest.raises(ToolError):
        pattern(strip([0]), min_coverage=0.5)  # needs an axis
    with pytest.raises(ToolError):
        pattern(strip([0]), min_count=3, max_count=1)


def test_a_job_without_the_template_is_refused_on_load():
    data = yaml.safe_load((FIXTURES / "job.yaml").read_text(encoding="utf-8"))
    data["geometry"] = {"rois": {"seam": {"relative_to": "frame", "rect": [0, 0.4, 1, 0.6]}}}
    data["tools"] = [{"id": "marca", "type": "pattern", "version": 1, "roi": "seam", "params": {"template": "patterns/logo.png"}, "reason_fail": "Marca ausente"}]
    job = Job.model_validate(data)
    check_job_tools(job, FILES)
    with pytest.raises(ToolError, match="missing files"):
        check_job_tools(job, {})


@pytest.mark.parametrize("seed", range(10))
def test_noise_never_crashes_and_rarely_matches(seed):
    noise = np.random.default_rng(seed).integers(0, 256, (60, 300, 3), dtype=np.uint8)
    r = pattern(noise, axis="x", max_gap=0.2)
    assert r.values["count"] == 0 and not r.passed


def test_measures():
    assert longest_run(np.array([1, 1, 0, 1, 1, 1, 0], bool)) == (3, 3)
    assert longest_run(np.zeros(4, bool)) == (0, 0)
    assert strip_profile(np.array([1, 0, 0, 1], bool)) == {"coverage": 0.5, "gap": 0.5, "gap_at": [0.25, 0.75]}
    assert strip_profile(np.zeros(0, bool))["gap"] == 1.0
    assert at_least(0.5, 1.0) == 0.5 and at_least(2, 1) == 1.0 and at_least(0, 0) == 1.0
    assert at_most(0.2, 0.1) == pytest.approx(0.8 / 0.9) and at_most(0.05, 0.1) == 1.0


def test_in_the_pipeline_a_short_print_fails_with_the_gap_in_the_reason():
    from vision_station.cameras import Frame
    from vision_station.jobs import CameraProfile
    from vision_station.pipeline import inspect_job
    from vision_station.results import Outcome
    from vision_station.store import JobBundle
    from vision_station.verification import make_reference_files

    def frame(at_x):
        img = np.full((300, 700, 3), 160, np.uint8)
        img[125:175] = strip(at_x, length=700)
        return img

    data = yaml.safe_load((FIXTURES / "job.yaml").read_text(encoding="utf-8"))
    data["quality"] = {"brightness": {"min": 30, "max": 250}, "sharpness_min_ratio": 0.5}
    data["geometry"] = {"rois": {"seam": {"relative_to": "frame", "rect": [0, 125 / 300, 1, 175 / 300]}}}
    data["tools"] = [{"id": "marca", "type": "pattern", "version": 1, "roi": "seam",
                      "params": {"template": "patterns/logo.png", "axis": "x", "max_gap": 0.1},
                      "reason_fail": "Marca ausente em {gap:.0%} da faixa"}]
    profile = CameraProfile.model_validate(yaml.safe_load((FIXTURES / "profile.yaml").read_text()))
    good = frame(range(0, 700, 70))
    bundle = JobBundle(Job.model_validate(data), profile, {**make_reference_files(good), **FILES})
    assert inspect_job(bundle, Frame(good, 0.0)).outcome is Outcome.PASS
    r = inspect_job(bundle, Frame(frame(range(0, 420, 70)), 0.0))
    assert r.outcome is Outcome.FAIL and r.reason == "Marca ausente em 40% da faixa" and r.scores["marca"] < 1
