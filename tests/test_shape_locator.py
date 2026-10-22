"""The shape locator: a pose that the rest of the program can use (VIA-0075 S2)."""

import cv2
import numpy as np
import pytest

from validation import perturb
from validation.cases.shape import _FRAME, _RECT
from vision_station.geometry.pose import cut
from vision_station.locators import LocatorError, run_locator

H, W = _FRAME.shape[:2]
X0, Y0, X1, Y1 = (round(v * n) for v, n in zip(_RECT, (W, H, W, H)))
TEMPLATE = _FRAME[Y0:Y1, X0:X1]
FILES = {"t.png": cv2.imencode(".png", TEMPLATE)[1].tobytes()}


def locate(frame, **params):
    return run_locator("shape", 1, frame, {"template": "t.png", **params}, FILES)


def correlation(a, b):
    return float(cv2.matchTemplate(a.astype(np.float32), b.astype(np.float32), cv2.TM_CCOEFF_NORMED).max())


@pytest.mark.parametrize("degrees", [-18.0, 7.0, 25.0])
def test_a_turned_part_is_cut_upright_from_the_pose_it_gives(degrees):
    """The point of a pose: the region taken out of the frame by it is the part as taught, whatever the turn."""
    frame = perturb.turn(_FRAME, degrees)
    fixture = locate(frame, angles=[-30, 30])
    assert fixture.angle == pytest.approx(degrees, abs=0.4) and fixture.scale == pytest.approx(1.0, abs=0.02)
    upright = cut(frame, (0.0, 0.0, 1.0, 1.0), fixture).image
    assert upright.shape[:2] == TEMPLATE.shape[:2] and correlation(upright, TEMPLATE) > 0.9


def test_a_larger_part_gives_its_scale_and_is_cut_to_the_taught_size():
    matrix = cv2.getRotationMatrix2D((W / 2, H / 2), 0, 1.12)
    frame = cv2.warpAffine(_FRAME, matrix, (W, H), borderMode=cv2.BORDER_REPLICATE)
    fixture = locate(frame, scales=[0.9, 1.2])
    assert fixture.scale == pytest.approx(1.12, abs=0.015)
    assert locate(frame, scales=[0.9, 1.05]) is None  # outside the range it is not this object


def test_the_box_is_the_taught_one_centred_where_the_part_is():
    fixture = locate(_FRAME)
    assert fixture.rect == pytest.approx(_RECT, abs=1 / 640)


def test_the_brightness_does_not_matter_and_a_colour_frame_is_the_same_as_a_gray_one():
    assert locate(perturb.brightness(_FRAME, 0.6)).rect == pytest.approx(_RECT, abs=1 / 640)
    assert locate(cv2.cvtColor(_FRAME, cv2.COLOR_BGR2GRAY)).rect == pytest.approx(_RECT, abs=1 / 640)


def test_a_search_area_that_cuts_the_part_does_not_find_it():
    assert locate(_FRAME, search=[0.0, 0.0, 0.45, 1.0]) is None
    assert locate(_FRAME, search=[0.2, 0.3, 0.8, 0.8]).rect == pytest.approx(_RECT, abs=1 / 640)


def test_a_template_that_is_flat_or_not_an_image_is_refused_not_ignored():
    flat = {"t.png": cv2.imencode(".png", np.full((40, 40), 120, np.uint8))[1].tobytes()}
    with pytest.raises(LocatorError, match="flat"):
        run_locator("shape", 1, _FRAME, {"template": "t.png"}, flat)
    with pytest.raises(LocatorError, match="not an image"):
        run_locator("shape", 1, _FRAME, {"template": "t.png"}, {"t.png": b"not a png"})


def test_a_frame_smaller_than_the_template_or_empty_has_no_part():
    assert locate(np.zeros((30, 30, 3), np.uint8)) is None and locate(np.zeros((0, 0), np.uint8)) is None
