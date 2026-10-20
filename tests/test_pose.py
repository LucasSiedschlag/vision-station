"""Fixtures with a pose and regions cut upright (architecture §14, TD-21, FR-INS-11)."""

import cv2
import numpy as np
import pytest

from vision_station.geometry.pose import Fixture, RegionOutside, compose, cut, inside, pixel_rect, region_in_frame

W, H = 640, 480
PART = (220, 180, 420, 300)  # the part as taught: 200 x 120 px, centred at (320, 240)


def scene() -> np.ndarray:
    """A bench with a part that has a gradient and some marks, so a wrong cut shows."""
    image = np.full((H, W, 3), 60, np.uint8)
    x0, y0, x1, y1 = PART
    ramp = np.linspace(80, 220, x1 - x0, dtype=np.uint8)
    image[y0:y1, x0:x1] = ramp[None, :, None]
    cv2.rectangle(image, (x0 + 20, y0 + 20), (x0 + 60, y0 + 50), (0, 0, 255), -1)  # a red mark, upper left
    cv2.circle(image, (x1 - 40, y1 - 30), 15, (255, 0, 0), -1)  # a blue dot, lower right
    return image


def turned(image: np.ndarray, angle: float, scale: float = 1.0) -> np.ndarray:
    """The same scene with the part turned counter-clockwise on the screen and magnified, about its centre."""
    matrix = cv2.getRotationMatrix2D((320.0, 240.0), angle, scale)
    return cv2.warpAffine(image, matrix, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(60, 60, 60))


def taught() -> Fixture:
    x0, y0, x1, y1 = PART
    return Fixture(rect=(x0 / W, y0 / H, x1 / W, y1 / H))


def mean_difference(a: np.ndarray, b: np.ndarray) -> float:
    assert a.shape == b.shape, (a.shape, b.shape)
    return float(np.abs(a.astype(int) - b.astype(int)).mean())


# --- the oracle: what the pipeline did before there were poses --------------------------------------------


def old_resolve(anchor_rect, roi_rect, shape):
    """`resolve_roi` as it was, for a region relative to the anchor (or to the frame when anchor_rect is None)."""
    if anchor_rect is None:
        rect = roi_rect
    else:
        ax0, ay0, ax1, ay1 = anchor_rect
        w, h = ax1 - ax0, ay1 - ay0
        x0, y0, x1, y1 = roi_rect
        rect = (ax0 + x0 * w, ay0 + y0 * h, ax0 + x1 * w, ay0 + y1 * h)
    height, width = shape[:2]
    px = (round(rect[0] * width), round(rect[1] * height), round(rect[2] * width), round(rect[3] * height))
    ok = not (px[2] - px[0] < 1 or px[3] - px[1] < 1 or px[0] < 0 or px[1] < 0 or px[2] > width or px[3] > height)
    return rect, px, ok


def test_an_upright_fixture_cuts_exactly_what_the_pipeline_cut_before():
    """FR-JOB-13's spirit without a migrator: the same rectangle, in fractions and in pixels, for thousands of cases."""
    rng = np.random.default_rng(7)
    shape = (H, W, 3)
    for _ in range(4000):
        ax0, ay0 = rng.uniform(0, 0.7, 2)
        anchor = (ax0, ay0, ax0 + rng.uniform(0.05, 1 - ax0), ay0 + rng.uniform(0.05, 1 - ay0))
        rx0, ry0 = rng.uniform(0, 0.8, 2)
        roi = (rx0, ry0, rx0 + rng.uniform(0.01, 1 - rx0), ry0 + rng.uniform(0.01, 1 - ry0))
        for fixture, base in ((Fixture(rect=anchor), anchor), (None, None)):
            rect, px, ok = old_resolve(base, roi, shape)
            assert region_in_frame(roi, fixture) == rect
            assert pixel_rect(rect, shape) == px and inside(px, shape) == ok


def test_the_fractional_offsets_of_a_template_match_round_the_same():
    shape = (H, W, 3)
    for x0 in np.linspace(100.0, 110.0, 81):  # a match at a fraction of a pixel: .5 must round as it always did
        anchor = (x0 / W, 50.3 / H, (x0 + 160) / W, (50.3 + 90) / H)
        roi = (0.25, 0.25, 0.75, 0.75)
        assert pixel_rect(region_in_frame(roi, Fixture(rect=anchor)), shape) == old_resolve(anchor, roi, shape)[1]


def test_an_upright_cut_is_the_slice_of_the_frame():
    image = scene()
    got = cut(image, (0.0, 0.0, 1.0, 1.0), taught())
    x0, y0, x1, y1 = got.px
    assert got.px == PART and np.array_equal(got.image, image[y0:y1, x0:x1])
    assert np.array_equal(got.to_frame, [[1, 0, x0], [0, 1, y0]])


# --- a turned part is judged as one that is straight ----------------------------------------------------


@pytest.mark.parametrize("angle", [-15, -7.5, 4, 10, 15])
def test_a_turned_part_is_cut_upright_like_the_straight_one(angle):
    straight = cut(scene(), (0.0, 0.0, 1.0, 1.0), taught()).image
    fixture = Fixture(rect=taught().rect, angle=angle)
    got = cut(turned(scene(), angle), (0.0, 0.0, 1.0, 1.0), fixture).image
    assert got.shape == straight.shape
    inner = (slice(6, -6), slice(6, -6))  # the 1-pixel border is interpolated against the bench
    assert mean_difference(got[inner], straight[inner]) < 6.0


def test_a_region_inside_the_turned_part_follows_it():
    """The red mark is in the upper left of the part: after turning, the region over it must still be red."""
    region = (0.1, 0.17, 0.3, 0.42)  # exactly the red mark: 40 x 30 px of the part
    for angle in (-15, 12):
        got = cut(turned(scene(), angle), region, Fixture(rect=taught().rect, angle=angle)).image
        red = ((got[..., 2] > 200) & (got[..., 0] < 60)).mean()
        assert red > 0.85, (angle, red)
    wrong = cut(turned(scene(), 15), region, taught()).image  # the same picture cut as if it were straight
    assert ((wrong[..., 2] > 200) & (wrong[..., 0] < 60)).mean() < 0.6


def test_a_part_larger_than_taught_is_cut_at_its_own_size():
    big = Fixture(rect=taught().rect, scale=1.25)
    got = cut(turned(scene(), 0.0, 1.25), (0.0, 0.0, 1.0, 1.0), big)
    assert got.image.shape[:2] == (round(120 * 1.25), round(200 * 1.25))
    small = cv2.resize(got.image, (200, 120), interpolation=cv2.INTER_AREA)
    straight = cut(scene(), (0.0, 0.0, 1.0, 1.0), taught()).image
    inner = (slice(8, -8), slice(8, -8))
    assert mean_difference(small[inner], straight[inner]) < 8.0


def test_a_turned_region_that_leaves_the_picture_is_outside():
    near_edge = Fixture(rect=(0.0, 0.3, 0.3, 0.6), angle=20)  # turning swings its corners off the left side
    with pytest.raises(RegionOutside):
        cut(scene(), (0.0, 0.0, 1.0, 1.0), near_edge)
    with pytest.raises(RegionOutside):
        cut(scene(), (0.0, 0.0, 1.0, 1.0), Fixture(rect=(0.5, 0.5, 1.2, 0.9)))


# --- a fixture inside another (a chain) ------------------------------------------------------------------


@pytest.mark.parametrize("angle", [0, -12, 9])
def test_a_fixture_found_in_the_cut_of_another_lands_where_it_is_in_the_frame(angle):
    image = turned(scene(), angle)
    parent = Fixture(rect=taught().rect, angle=angle)
    got = cut(image, (0.0, 0.0, 1.0, 1.0), parent)
    # find the red mark in the upright cut, as a locator working on it would
    mask = (got.image[..., 2] > 200) & (got.image[..., 0] < 60)
    ys, xs = np.nonzero(mask)
    mark = Fixture(rect=((xs.min() - 0.5) / got.image.shape[1], (ys.min() - 0.5) / got.image.shape[0], (xs.max() + 1.5) / got.image.shape[1], (ys.max() + 1.5) / got.image.shape[0]), name="mark")
    placed = compose(got, parent, mark, image.shape)
    # where the mark really is in the turned frame
    frame_mask = (image[..., 2] > 200) & (image[..., 0] < 60)
    fys, fxs = np.nonzero(frame_mask)
    cx, cy = placed.centre
    assert abs(cx * W - fxs.mean()) < 1.5 and abs(cy * H - fys.mean()) < 1.5
    assert placed.angle == pytest.approx(angle) and placed.name == "mark"
