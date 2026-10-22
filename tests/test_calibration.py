"""Calibration px to mm (FR-INS-15, architecture §14.4, VIA-0075 C1)."""

import numpy as np
import pytest
import yaml
from pydantic import BaseModel, ConfigDict, Field

from test_verification import make_bundle
from vision_station.algorithms.calibration import calibrate_known_dimension
from vision_station.core.calibration import CALIBRATION_FILE, Calibration, Scale
from vision_station.core.jobfiles import JobFileError, JobFiles
from vision_station.geometry.pose import Fixture, cut
from vision_station.store.errors import FormatError
from vision_station.store.bundle import bundle_from_files
from vision_station.tools import ToolError, ToolType, check_job_tools, register
from vision_station.tools.base import ToolResult, judged, minimum, uses_millimetres


def calibration_file(**over) -> bytes:
    return yaml.safe_dump({"method": "known_dimension", "mm_per_px": 0.25, "date": "2026-10-22", "residual_mm": 0.0, **over}).encode()


def test_a_known_dimension_gives_the_scale():
    assert calibrate_known_dimension(200, 50) == (0.25, 0.0)


def test_several_known_dimensions_give_the_best_scale_and_the_worst_miss():
    scale, residual = calibrate_known_dimension([100, 200, 400], [25.5, 50, 99.5])
    assert scale == pytest.approx(0.2492, abs=1e-3)  # a line through the origin
    assert 0 < residual < 1


@pytest.mark.parametrize("pixels,millimetres", [(0, 10), (-5, 10), (10, 0), (10, -1), (float("nan"), 10), (10, float("inf")), ([], []), ([1, 2], [1])])
def test_a_dimension_that_is_not_one_is_refused(pixels, millimetres):
    with pytest.raises(ValueError):
        calibrate_known_dimension(pixels, millimetres)


def test_the_calibration_file_has_one_scale_or_x_and_y():
    one = Calibration.model_validate(yaml.safe_load(calibration_file()))
    assert one.scale == Scale(0.25, 0.25)
    two = Calibration.model_validate(yaml.safe_load(calibration_file(mm_per_px=[0.25, 0.3])))
    assert two.scale == Scale(0.25, 0.3)


@pytest.mark.parametrize("over", [{"mm_per_px": 0}, {"mm_per_px": [0.1, 0.2, 0.3]}, {"mm_per_px": [0.1, -1]}, {"method": "checkerboard"}, {"extra": 1}, {"date": "yesterday"}])
def test_a_calibration_that_is_not_one_is_refused(over):
    with pytest.raises(ValueError):
        Calibration.model_validate(yaml.safe_load(calibration_file(**over)))


def test_the_tools_read_the_scale_from_the_job_files():
    assert JobFiles({CALIBRATION_FILE: calibration_file()}).scale() == Scale(0.25, 0.25)
    with pytest.raises(JobFileError, match="calibrat"):
        JobFiles({}).scale()
    with pytest.raises(JobFileError):
        JobFiles({CALIBRATION_FILE: b"mm_per_px: 0"}).scale()


# --- a parameter in millimetres needs a calibrated job ------------------------------------------------

class _MmParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    width_mm: float | None = Field(None, json_schema_extra={"x-level": 1, "x-group": "criteria", "x-unit": "mm"})
    limit: int = Field(1, json_schema_extra={"x-level": 1, "x-group": "criteria", "x-unit": "count"})


def _run(region: np.ndarray, params: _MmParams, files: JobFiles) -> ToolResult:
    return judged([minimum("min", "width", files.scale().x if params.width_mm else 1.0, 0.0)])


@pytest.fixture(autouse=True)
def _the_fake_tool():
    """Registered for these tests only: other tests list the tool types."""
    from vision_station.tools.base import _REGISTRY

    register(ToolType(name="mm_fake", version=1, params=_MmParams, run=_run))
    yield
    _REGISTRY.pop(("mm_fake", 1), None)


def _job(params: dict):
    bundle = make_bundle()
    data = bundle.job.model_dump(mode="json")
    data["tools"] = [{"id": "w", "type": "mm_fake", "version": 1, "roi": bundle.job.tools[0].roi, "reason_fail": "x", "params": params}]
    return data, bundle


def test_a_parameter_in_millimetres_is_recognised_only_when_it_is_given():
    from vision_station.tools import get_tool

    tool = get_tool("mm_fake", 1)
    assert uses_millimetres(tool, _MmParams(width_mm=2.0)) and not uses_millimetres(tool, _MmParams()) and not uses_millimetres(tool, _MmParams(limit=3))


def test_a_job_with_a_limit_in_millimetres_and_no_calibration_is_refused():
    from vision_station.jobs import Job

    data, bundle = _job({"width_mm": 2.0})
    files = {n: d for n, d in bundle.extra.items()}
    with pytest.raises(ToolError, match="calibration"):
        check_job_tools(Job.model_validate(data), files)
    check_job_tools(Job.model_validate(data), {**files, CALIBRATION_FILE: calibration_file()})  # calibrated: fine
    data, _ = _job({"limit": 2})
    check_job_tools(Job.model_validate(data), files)  # nothing in millimetres: fine


def test_loading_a_job_checks_the_calibration_file_too():
    from vision_station.store.archive import MANIFEST  # noqa: F401  (the files of a bundle, as the store keeps them)

    data, bundle = _job({"width_mm": 2.0})
    base = bundle.files()
    base["job.yaml"] = yaml.safe_dump(data).encode()
    with pytest.raises(FormatError, match="calibration"):
        bundle_from_files(base)
    calibrated = {**base, CALIBRATION_FILE: calibration_file()}
    data["acquisition"]["image"]["calibration"] = CALIBRATION_FILE
    calibrated["job.yaml"] = yaml.safe_dump(data).encode()
    assert bundle_from_files(calibrated).job.tools[0].params == {"width_mm": 2.0}
    broken = {**calibrated, CALIBRATION_FILE: b"mm_per_px: -1"}
    with pytest.raises(FormatError, match="calibration"):
        bundle_from_files(broken)
    elsewhere = {**calibrated, "camera/other.yaml": calibration_file()}
    data["acquisition"]["image"]["calibration"] = "camera/other.yaml"
    elsewhere["job.yaml"] = yaml.safe_dump(data).encode()
    with pytest.raises(FormatError, match=CALIBRATION_FILE):
        bundle_from_files(elsewhere)


# --- the pixels of a region cut are the frame's pixels, whatever the scale of the fixture ----------------

@pytest.mark.parametrize("angle,scale", [(0.0, 1.0), (0.0, 1.5), (20.0, 1.0), (20.0, 0.8)])
def test_a_region_cut_keeps_the_pixels_of_the_frame_so_the_scale_of_a_fixture_does_not_change_mm_per_px(angle, scale):
    frame = np.zeros((600, 800, 3), np.uint8)
    fixture = Fixture(rect=(0.25, 0.25, 0.75, 0.75), angle=angle, scale=scale)
    region = cut(frame, (0.0, 0.0, 1.0, 1.0), fixture)
    # one pixel of the cut is one pixel of the frame: the map to the frame is a rotation and a shift, with no zoom
    assert abs(np.linalg.det(region.to_frame[:, :2]) - 1.0) < 1e-9
    # ...and it is the part, `scale` times larger (or smaller) than it was taught, that is cut: 400 x 300 px taught
    assert region.image.shape[:2] == (round(300 * scale), round(400 * scale))
