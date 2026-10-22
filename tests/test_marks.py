"""The mark contract (VIA-0124, FR-PLT-10): a tool names shapes in its region's pixels, the pipeline maps them to the frame."""

import numpy as np
import pytest

from vision_station.core.results import MAX_MARK_POINTS, MAX_MARKS, Mark, ToolReport, tool_dict
from vision_station.geometry.pose import Fixture, cut
from vision_station.pipeline.marks import to_frame_marks, valid_mark
from vision_station.tools.base import ToolResult

FRAME = np.zeros((200, 400, 3), np.uint8)  # 400 wide, 200 high: fractions of x and y are not the same pixels


def straight():
    return cut(FRAME, (0.25, 0.25, 0.75, 0.75), None)  # 200 x 100 px at (100, 50)


def rect(x0, y0, x1, y1, role="found"):
    return Mark("rect", role, ((x0, y0), (x1, y1)))


def test_a_mark_of_a_straight_region_is_a_fraction_of_the_frame():
    got = to_frame_marks((rect(0, 0, 100, 50),), straight(), FRAME.shape)
    assert got == (Mark("rect", "found", ((0.25, 0.25), (0.5, 0.5))),)


def test_a_point_and_a_text_keep_their_kind_and_role():
    marks = (Mark("point", "expected", ((10.0, 20.0),)), Mark("text", "found", ((10.0, 20.0),), text="A1"))
    got = to_frame_marks(marks, straight(), FRAME.shape)
    assert [(m.kind, m.role, m.text) for m in got] == [("point", "expected", ""), ("text", "found", "A1")]
    assert got[0].points == ((0.275, 0.35),)


def test_a_rect_of_a_turned_region_becomes_a_closed_poly_with_the_four_corners():
    region = cut(FRAME, (0.25, 0.25, 0.75, 0.75), Fixture(rect=(0.0, 0.0, 1.0, 1.0), angle=10.0))
    (got,) = to_frame_marks((rect(0, 0, 50, 20),), region, FRAME.shape)
    assert got.kind == "poly" and got.closed and len(got.points) == 4
    matrix = region.to_frame
    expected = [matrix @ np.array([x, y, 1.0]) for x, y in ((0, 0), (50, 0), (50, 20), (0, 20))]
    for (fx, fy), (ex, ey) in zip(got.points, expected, strict=True):
        assert fx == pytest.approx(ex / 400, abs=1e-4) and fy == pytest.approx(ey / 200, abs=1e-4)


def test_coordinates_have_four_decimals():
    (got,) = to_frame_marks((Mark("point", "found", ((1 / 3, 2 / 3),)),), straight(), FRAME.shape)
    assert all(len(str(v).split(".")[1]) <= 4 for v in got.points[0])


def test_no_more_than_the_cap_and_the_first_ones_stay():
    marks = tuple(Mark("point", "found", ((float(i), 1.0),)) for i in range(MAX_MARKS + 10))
    got = to_frame_marks(marks, straight(), FRAME.shape)
    assert len(got) == MAX_MARKS
    assert got[0].points[0][0] == pytest.approx(100 / 400) and got[-1].points[0][0] == pytest.approx((100 + MAX_MARKS - 1) / 400, abs=1e-4)


@pytest.mark.parametrize("mark", [
    Mark("rect", "found", ((0, 0),)),  # a rect has two corners
    Mark("point", "found", ((0, 0), (1, 1))),
    Mark("text", "found", ((0, 0),), text=""),  # nothing to write
    Mark("poly", "found", ((0, 0),)),  # a line has two points at least
    Mark("poly", "found", tuple((float(i), 0.0) for i in range(MAX_MARK_POINTS + 1))),  # not truncated: refused
    Mark("point", "found", ((float("nan"), 1.0),)),
    Mark("point", "found", ((float("inf"), 1.0),)),
    Mark("point", "found", ((500.0, 10.0),)),  # outside the region (200 x 100)
    Mark("rect", "found", ((-5.0, 0.0), (10.0, 10.0))),
    Mark("circle", "found", ((0, 0),)),  # unknown kind
    Mark("point", "paint", ((0, 0),)),  # unknown role
])
def test_an_invalid_mark_is_refused(mark):
    assert not valid_mark(mark, (100, 200))


def test_half_a_pixel_outside_is_not_outside():
    assert valid_mark(Mark("point", "found", ((200.4, 100.4),)), (100, 200))
    assert not valid_mark(Mark("point", "found", ((200.6, 50.0),)), (100, 200))


def test_an_invalid_mark_is_dropped_and_the_others_stay():
    good, bad = rect(1, 1, 5, 5), Mark("point", "found", ((float("nan"), 0.0),))
    assert len(to_frame_marks((bad, good, bad), straight(), FRAME.shape)) == 1


def test_a_tool_result_has_no_marks_unless_it_gives_them():
    assert ToolResult(True, 1.0).marks == ()


def test_the_report_carries_the_marks_to_the_contract_dict():
    mark = Mark("rect", "defect", ((0.1, 0.2), (0.3, 0.4)))
    report = ToolReport("t1", "color", 1, False, 0.0, marks=(mark,))
    assert tool_dict(report)["marks"] == [{"kind": "rect", "role": "defect", "points": [[0.1, 0.2], [0.3, 0.4]], "closed": True, "text": ""}]
    assert tool_dict(ToolReport("t2", "color", 1, True, 1.0))["marks"] == []


def _with_marks(monkeypatch, marks):
    """The code tool as it is, plus the marks `marks` (a stand-in until the tools draw: the wiring is what is tested)."""
    from dataclasses import replace

    from vision_station.pipeline import inspect as pipeline

    real = pipeline.run_tool
    monkeypatch.setattr(pipeline, "run_tool", lambda *a, **k: replace(real(*a, **k), marks=marks))


@pytest.mark.parametrize("scene,outcome", [("good", "PASS"), ("none", "FAIL")])
def test_the_marks_reach_the_result_for_a_pass_and_for_a_fail(monkeypatch, scene, outcome):
    from test_pipeline import frame
    from test_verification import make_bundle, no_code_scene, qr_scene
    from vision_station.pipeline import inspect_job

    _with_marks(monkeypatch, (Mark("rect", "found", ((32.0, 24.0), (160.0, 120.0))),))  # the region is the whole 320 x 240 frame
    result = inspect_job(make_bundle(), frame(qr_scene("LOTE-1") if scene == "good" else no_code_scene()))
    assert str(result.outcome) == outcome
    assert result.tools[0].marks == (Mark("rect", "found", ((0.1, 0.1), (0.5, 0.5))),)


def test_an_invalid_mark_never_changes_the_verdict(monkeypatch):
    from test_pipeline import frame
    from test_verification import make_bundle, qr_scene
    from vision_station.pipeline import inspect_job

    _with_marks(monkeypatch, (Mark("point", "found", ((float("nan"), 0.0),)),))
    result = inspect_job(make_bundle(), frame(qr_scene("LOTE-1")))
    assert str(result.outcome) == "PASS" and result.tools[0].marks == ()


def _overlay(*marks, passed=False):
    from vision_station.core.results import InspectionResult, Outcome
    from vision_station.pipeline import draw_overlay

    result = InspectionResult(Outcome.FAIL, tools=(ToolReport("t", "color", 1, passed, 0.0, marks=marks),))
    return draw_overlay(np.zeros((100, 200, 3), np.uint8), result)


def _lit(image, x, y, radius=3):
    """The colour near the pixel (x, y), as the brightest channel triple found there."""
    patch = image[max(0, y - radius) : y + radius + 1, max(0, x - radius) : x + radius + 1].reshape(-1, 3)
    return tuple(int(v) for v in patch[patch.sum(axis=1).argmax()])


def test_the_saved_picture_draws_the_marks_in_the_colour_of_their_role():
    image = _overlay(
        Mark("rect", "defect", ((0.1, 0.2), (0.4, 0.6))),  # (20, 20) to (80, 60)
        Mark("poly", "found", ((0.6, 0.2), (0.9, 0.2), (0.9, 0.8)), closed=False),
        Mark("point", "expected", ((0.5, 0.9),)),
        Mark("text", "defect", ((0.1, 0.9),), text="LOTE-2"),
    )
    assert _lit(image, 20, 40) == (50, 50, 230)  # a defect: red (BGR)
    assert _lit(image, 80, 60) == (50, 50, 230)
    assert _lit(image, 180, 20) == (50, 50, 230)  # what a tool that failed found is red too: the verdict gives the colour
    assert image[85:95, 15:75].any()  # the text is there
    assert _lit(image, 100, 90) != (0, 0, 0)  # the expected point


def test_what_a_passing_tool_found_is_green_and_a_picture_without_marks_is_as_before():
    green = _overlay(Mark("rect", "found", ((0.1, 0.2), (0.4, 0.6))), passed=True)
    assert _lit(green, 20, 40) == (60, 190, 60)
    assert not _overlay().any()  # no region to draw in this result, no marks: nothing at all


def test_what_an_informative_tool_found_is_not_drawn_as_the_failure_of_the_part():
    from vision_station.core.results import InspectionResult, Outcome
    from vision_station.pipeline import draw_overlay

    mark = Mark("rect", "defect", ((0.1, 0.2), (0.4, 0.6)))
    tool = ToolReport("t", "color", 1, False, 0.0, affects_result=False, marks=(mark,))
    image = draw_overlay(np.zeros((100, 200, 3), np.uint8), InspectionResult(Outcome.PASS, tools=(tool,)))
    assert _lit(image, 20, 40) == (0, 200, 240)  # yellow, as the region of an informative tool
