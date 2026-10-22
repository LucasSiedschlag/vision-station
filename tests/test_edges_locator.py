"""The edges locator: the corner of two edges, its angle and the pose it gives (VIA-0075 E3)."""

import cv2
import numpy as np
import pytest

from validation import perturb
from validation.cases.edges import CORNER, HORIZONTAL, PARAMS, VERTICAL, box
from validation.scenes import bench
from vision_station.locators import run_locator


def locate(frame, **over):
    return run_locator("edges", 1, frame, {**PARAMS, **over}, {})


def test_the_corner_and_the_box_are_found_to_a_pixel_on_the_bench():
    frame, rect = bench(printed=False, at=(260, 205))
    fixture = locate(frame)
    assert fixture.rect == pytest.approx(rect, abs=1 / 640) and fixture.angle == pytest.approx(0, abs=0.2) and fixture.score > 0.95


@pytest.mark.parametrize("degrees", [-8.0, 3.0, 10.0])
def test_a_turned_part_gives_its_angle_to_half_a_degree_and_its_centre(degrees):
    frame, rect = bench(printed=False)
    fixture = locate(perturb.turn(frame, degrees))
    assert fixture.angle == pytest.approx(degrees, abs=0.5)
    cx, cy = (rect[0] + rect[2]) / 2, (rect[1] + rect[3]) / 2
    assert fixture.centre == pytest.approx((cx, cy), abs=2 / 640)


def test_a_light_part_on_a_dark_bench_is_the_other_polarity():
    frame, rect = bench(printed=False)
    inverted = 255 - frame
    fixture = locate(inverted, vertical={**VERTICAL, "polarity": "rising"}, horizontal={**HORIZONTAL, "polarity": "rising"})
    assert fixture.rect == pytest.approx(rect, abs=1 / 640)


def test_a_wrong_polarity_finds_nothing():
    frame, _ = bench(printed=False)
    assert locate(frame, vertical={**VERTICAL, "polarity": "rising"}) is None


def test_a_speck_in_one_slice_does_not_tilt_the_edge():
    frame, rect = bench(printed=False)
    frame[238:243, 230:250] = 20  # a dark scratch across the edge in one slice of the vertical window
    fixture = locate(frame)
    assert fixture.angle == pytest.approx(0, abs=0.3) and fixture.rect == pytest.approx(rect, abs=1.5 / 640)


def test_a_corner_that_is_not_square_is_not_found():
    frame, _ = bench(printed=False)
    sheared = cv2.warpAffine(frame, np.float32([[1, 0.25, -50], [0, 1, 0]]), (640, 480), borderMode=cv2.BORDER_REPLICATE)  # the left edge leans 14°
    assert locate(sheared) is None


def test_windows_that_miss_the_edges_find_nothing_not_something_else():
    frame, _ = bench(printed=False)
    assert locate(frame, vertical={**VERTICAL, "rect": box(20, 225, 120, 280)}) is None
    assert locate(frame, horizontal={**HORIZONTAL, "rect": box(280, 20, 380, 100)}) is None
    assert locate(np.zeros((6, 6, 3), np.uint8)) is None and locate(np.zeros((0, 0), np.uint8)) is None


def test_a_gray_frame_works_as_well_as_a_colour_one():
    frame, rect = bench(printed=False)
    assert locate(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)).rect == pytest.approx(rect, abs=1 / 640)
    assert CORNER == (rect[0], rect[1])
