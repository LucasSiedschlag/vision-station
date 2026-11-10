"""The circles tool (FR-PLT-9): what the validation bench does not say in words."""

import cv2
import numpy as np
import pytest

from vision_station.algorithms.circles import find_circles
from vision_station.tools import ToolError, run_tool, validate_params


def rings(*centres, radius=24, double=False):
    image = np.full((200, 300), 110, np.uint8)
    for x, y in centres:
        cv2.circle(image, (x, y), radius, 210, 5, cv2.LINE_AA)
        if double:
            cv2.circle(image, (x, y), radius - 9, 210, 2, cv2.LINE_AA)
    return image


def test_the_two_edges_of_a_ring_are_one_circle_even_when_the_detector_gives_both():
    # OpenCV's HOUGH_GRADIENT_ALT returns one centre at two radii; the algorithm keeps the best and drops the other
    found = find_circles(rings((60, 60), (150, 60), double=True), radius_min=12, radius_max=32, min_distance=24, min_roundness=0.7)
    assert len(found) == 2


def test_the_minimum_distance_defaults_to_twice_the_smallest_radius_and_can_be_raised():
    two = rings((60, 60), (150, 60), radius=24)  # 90 px apart: more than 2 x 24
    params = {"radius_min": 18, "radius_max": 32, "min_count": 0}
    assert run_tool("circles", 1, two, params).values["count"] == 2
    # a larger distance than their spacing: the second is dropped as the same part as the first
    assert run_tool("circles", 1, two, {**params, "min_distance": 120}).values["count"] == 1


def test_too_many_is_drawn_as_the_defect_and_too_few_is_not():
    three = rings((50, 50), (150, 50), (250, 50))
    many = run_tool("circles", 1, three, {"radius_min": 18, "radius_max": 32, "max_count": 2})
    assert not many.passed and {m.role for m in many.marks} == {"defect"} and len(many.marks) == 3
    few = run_tool("circles", 1, three, {"radius_min": 18, "radius_max": 32, "min_count": 4})
    assert not few.passed and {m.role for m in few.marks} == {"found"}


def test_a_region_smaller_than_a_circle_has_none_and_an_empty_one_is_an_error():
    assert run_tool("circles", 1, np.zeros((20, 20), np.uint8), {"radius_min": 30, "radius_max": 40, "min_count": 0}).values["count"] == 0
    with pytest.raises(ToolError):
        run_tool("circles", 1, np.zeros((0, 0), np.uint8), {"radius_min": 10, "radius_max": 20, "min_count": 1})


@pytest.mark.parametrize("params", ({"radius_min": 10, "radius_max": 20}, {"radius_min": 30, "radius_max": 20, "min_count": 1}))
def test_the_parameters_that_cannot_work_are_refused(params):
    with pytest.raises(ToolError):
        validate_params("circles", 1, params)


def test_a_colour_picture_is_read_by_its_gray_levels():
    bgr = cv2.cvtColor(rings((60, 60), (150, 60)), cv2.COLOR_GRAY2BGR)
    assert run_tool("circles", 1, bgr, {"radius_min": 18, "radius_max": 32, "min_count": 2, "max_count": 2}).passed


def test_more_circles_than_the_tool_counts_is_an_error_not_a_truncated_count():
    # 224 separated rings: judging a count cut at 200 would pass min_count 200 and max_count 200 (never a false PASS)
    image = np.full((720, 800), 110, np.uint8)
    for row in range(14):
        for col in range(16):
            cv2.circle(image, (30 + col * 50, 30 + row * 50), 18, 210, 3, cv2.LINE_AA)
    with pytest.raises(ToolError):
        run_tool("circles", 1, image, {"radius_min": 14, "radius_max": 22, "min_count": 200, "max_count": 200})


@pytest.mark.parametrize("roundness", (1, 1.0, 1.5))
def test_a_roundness_of_one_or_more_is_refused(roundness):
    # the circle search (HOUGH_GRADIENT_ALT) needs a score below 1: a setting it cannot run must not pass validation
    with pytest.raises(ToolError):
        validate_params("circles", 1, {"radius_min": 10, "radius_max": 20, "min_count": 1, "min_roundness": roundness})


def test_a_roundness_just_below_one_is_accepted_and_runs():
    result = run_tool("circles", 1, rings((60, 60), (150, 60)), {"radius_min": 18, "radius_max": 32, "min_count": 0, "min_roundness": 0.99})
    assert result.values["count"] >= 0
