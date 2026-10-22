"""Shape matching: gradient-direction matching over a pyramid (VIA-0075 S1, TD-25).

The acceptance of the algorithm, before the tool and the locator that use it: the pose to a fraction of a pixel and of a degree,
under light and noise, with a part hidden, a reversed polarity, two instances and nothing there.
"""

import time

import cv2
import numpy as np
import pytest

from validation import perturb
from vision_station.algorithms.shapematch import Match, build_model, find_shapes

H, W = 240, 320
CENTRE = (W / 2, H / 2)  # the index of the pixel the scenes turn about (validation.perturb.turn)
R = 40  # the template is (2R + 1) pixels square, its centre the part's


def part(canvas: np.ndarray, centre: tuple[float, float], scale: float = 1.0) -> None:
    """An asymmetric dark part drawn on a light canvas: a plate with a notch, a hole and an L-shaped mark."""
    cx, cy = centre
    p = lambda x, y: (round(cx + x * scale), round(cy + y * scale))  # noqa: E731
    cv2.rectangle(canvas, p(-34, -22), p(34, 22), 60, -1)
    cv2.rectangle(canvas, p(20, -22), p(34, -8), 210, -1)  # a notch in a corner
    cv2.circle(canvas, p(-16, 4), max(2, round(7 * scale)), 210, -1, cv2.LINE_AA)  # a hole off the centre
    cv2.line(canvas, p(2, -12), p(2, 12), 210, max(1, round(4 * scale)))  # an L
    cv2.line(canvas, p(2, 12), p(22, 12), 210, max(1, round(4 * scale)))


def scene(angle: float = 0.0, scale: float = 1.0, background: int = 200) -> np.ndarray:
    canvas = np.full((H, W), background, np.uint8)
    part(canvas, CENTRE)
    matrix = cv2.getRotationMatrix2D(CENTRE, angle, scale)
    return cv2.warpAffine(canvas, matrix, (W, H), flags=cv2.INTER_LINEAR, borderValue=background)


def template() -> np.ndarray:
    base = scene()
    cx, cy = int(CENTRE[0]), int(CENTRE[1])
    return base[cy - R : cy + R + 1, cx - R : cx + R + 1].copy()


MODEL = build_model(template())


def best(image: np.ndarray, **kw) -> Match:
    found = find_shapes(image, MODEL, **{"angles": (-60, 60), "scales": (0.85, 1.15), **kw})
    assert found, "nothing found"
    return found[0]


def test_a_part_as_taught_is_found_where_it_is():
    match = best(scene())
    assert (match.x, match.y) == pytest.approx(CENTRE, abs=0.3) and match.angle == pytest.approx(0, abs=0.2)
    assert match.scale == pytest.approx(1.0, abs=0.01) and match.score > 0.97


@pytest.mark.parametrize("angle", [-30.0, 7.5, 45.0])
@pytest.mark.parametrize("scale", [0.93, 1.0, 1.08])
def test_the_pose_is_given_to_a_third_of_a_degree_and_a_third_of_a_pixel(angle, scale):
    # the score is flat to 3e-4 within 0.2 degrees of the pose of a picture made by interpolation: a third of a degree is what is real
    match = best(scene(angle, scale), angles=(-60, 60), scales=(0.85, 1.15))
    assert match.angle == pytest.approx(angle, abs=0.3)
    assert (match.x, match.y) == pytest.approx(CENTRE, abs=0.3)
    assert match.scale == pytest.approx(scale, abs=0.01)


def test_the_same_precision_under_noise_and_a_change_of_light():
    for image in (perturb.noise(scene(20, 1.05)), perturb.brightness(scene(20, 1.05), 0.85), perturb.brightness(scene(20, 1.05), 1.15)):
        match = best(image)
        assert match.angle == pytest.approx(20, abs=0.3) and (match.x, match.y) == pytest.approx(CENTRE, abs=0.4) and match.scale == pytest.approx(1.05, abs=0.015)


def test_a_part_off_the_centre_is_found_where_it_is():
    canvas = np.full((H, W), 200, np.uint8)
    part(canvas, (90.0, 70.0))
    match = best(canvas)
    assert (match.x, match.y) == pytest.approx((90, 70), abs=0.3)


def test_a_part_a_quarter_hidden_is_found_with_a_score_that_says_so():
    image = scene(12, 1.0)
    image[:, : int(CENTRE[0]) - 12] = 200  # the left quarter of the plate is gone
    clean, hidden = best(scene(12, 1.0)), best(image, min_score=0.5)
    assert hidden.angle == pytest.approx(12, abs=0.6) and (hidden.x, hidden.y) == pytest.approx(CENTRE, abs=1.0)
    assert 0.6 < hidden.score < clean.score - 0.08


def test_a_reversed_polarity_is_found_only_when_it_is_asked_to_be_ignored():
    reversed_ = 255 - scene(15, 1.0)
    assert find_shapes(reversed_, MODEL, angles=(-60, 60), scales=(0.9, 1.1), min_score=0.7) == []
    match = best(reversed_, polarity="ignore", min_score=0.7)
    assert match.angle == pytest.approx(15, abs=0.3) and match.score > 0.95


def test_two_instances_are_both_found_and_the_best_comes_first():
    canvas = np.full((H, W), 200, np.uint8)
    part(canvas, (80.0, 70.0))
    part(canvas, (230.0, 160.0))
    canvas[150:175, 215:245] = np.maximum(canvas[150:175, 215:245], 130)  # the second is a little spoiled
    found = find_shapes(canvas, MODEL, angles=(-10, 10), scales=(0.95, 1.05), max_instances=3)
    assert len(found) == 2 and found[0].score >= found[1].score
    assert sorted((round(m.x), round(m.y)) for m in found) == [(80, 70), (230, 160)]


def test_nothing_is_found_in_an_empty_or_flat_picture_or_one_with_other_things():
    assert find_shapes(np.full((H, W), 200, np.uint8), MODEL) == []
    noise = np.random.default_rng(2).integers(0, 255, (H, W), dtype=np.uint8)
    assert find_shapes(noise, MODEL) == []
    other = np.full((H, W), 200, np.uint8)
    cv2.circle(other, (160, 120), 30, 60, -1)
    cv2.rectangle(other, (40, 40), (90, 90), 60, 3)
    assert find_shapes(other, MODEL) == []


def test_a_scale_outside_the_range_is_not_found_and_inside_it_is():
    big = scene(0, 1.25)
    assert find_shapes(big, MODEL, scales=(0.9, 1.1)) == []
    assert best(big, scales=(1.1, 1.4)).scale == pytest.approx(1.25, abs=0.015)


def test_the_angle_range_limits_the_search_and_a_full_turn_finds_any_angle():
    turned = scene(150, 1.0)
    assert find_shapes(turned, MODEL, angles=(-30, 30), scales=(1, 1)) == []
    match = best(turned, angles=(-180, 180), scales=(1, 1))
    assert match.angle == pytest.approx(150, abs=0.3)


def test_the_result_is_the_same_twice():
    image = scene(33, 0.97)
    assert find_shapes(image, MODEL, angles=(-60, 60), scales=(0.85, 1.15)) == find_shapes(image, MODEL, angles=(-60, 60), scales=(0.85, 1.15))


def test_a_pattern_that_does_not_fit_in_the_picture_or_a_flat_template_is_refused():
    with pytest.raises(ValueError, match="flat"):
        build_model(np.full((50, 50), 100, np.uint8))
    with pytest.raises(ValueError):
        build_model(np.zeros((6, 6), np.uint8))
    assert find_shapes(np.zeros((20, 20), np.uint8), MODEL) == []  # the pattern is larger than the picture
