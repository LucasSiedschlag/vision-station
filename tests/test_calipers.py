"""The calipers: where the edges of a profile are, to a fraction of a pixel (VIA-0075 E1)."""

import cv2
import numpy as np
import pytest

from vision_station.algorithms.calipers import find_edges, gradient, profile


def bar(start=20, stop=140, length=200, low=40.0, high=200.0):
    """A profile that is `low` with a bar of `high` over the pixels start..stop-1."""
    values = np.full(length, low)
    values[start:stop] = high
    return values


def test_a_bar_of_120_pixels_is_120_wide_between_its_edges():
    rising, falling = find_edges(bar())
    assert rising.rising and not falling.rising
    assert rising.position == pytest.approx(19.5, abs=0.02) and falling.position == pytest.approx(139.5, abs=0.02)
    assert falling.position - rising.position == pytest.approx(120, abs=0.05)


def test_the_contrast_is_the_height_of_the_step_whatever_the_smoothing():
    for sigma in (1.0, 1.5, 2.0, 3.0):  # under one pixel the step is not smooth any more and the height is only approximate
        (edge, _) = find_edges(bar(low=40, high=140), sigma=sigma, min_contrast=5)
        assert edge.contrast == pytest.approx(100, rel=0.06), sigma


def test_a_narrow_bar_keeps_the_contrast_of_both_edges():
    edges = find_edges(bar(start=50, stop=53), sigma=0.7, min_contrast=50)
    assert len(edges) == 2 and edges[1].position - edges[0].position == pytest.approx(3, abs=0.1)


def test_an_edge_between_pixels_is_found_to_a_twentieth_of_a_pixel():
    values = np.zeros(100)
    values[51:] = 100
    values[50] = 70  # the step is at 50.3 in a picture whose pixel i covers [i, i+1]: 49.8 at pixel centres
    (edge,) = find_edges(values)
    assert edge.position + 0.5 == pytest.approx(50.3, abs=0.05)


def test_a_blurred_bar_is_the_same_width():
    blurred = cv2.GaussianBlur(bar().reshape(1, -1), (0, 0), 2).ravel()
    rising, falling = find_edges(blurred, sigma=2.0)
    assert falling.position - rising.position == pytest.approx(120, abs=0.2)


def test_polarity_is_dark_to_light_in_the_direction_of_the_profile():
    assert [e.rising for e in find_edges(bar())] == [True, False]
    assert [e.rising for e in find_edges(bar(), polarity="rising")] == [True]
    assert [e.rising for e in find_edges(bar(), polarity="falling")] == [False]
    assert [e.rising for e in find_edges(bar(low=200, high=40))] == [False, True]  # a dark bar on light
    assert [e.rising for e in find_edges(bar()[::-1])] == [True, False]  # read the other way, the same bar is again dark-light-dark


def test_a_step_below_the_minimum_contrast_is_not_an_edge():
    assert find_edges(bar(low=100, high=110), min_contrast=20) == []
    assert len(find_edges(bar(low=100, high=110), min_contrast=5)) == 2


def test_a_flat_or_tiny_profile_has_no_edge_and_the_ends_are_not_edges():
    assert find_edges(np.full(100, 80.0)) == [] and find_edges(np.array([1.0, 200.0])) == []
    assert find_edges(bar(start=1, stop=140)) == [find_edges(bar(start=1, stop=140))[-1]]  # the step at the very start is lost, the other found


def test_noise_does_not_move_an_edge_by_more_than_a_tenth_of_a_pixel():
    rng = np.random.default_rng(3)
    region = np.tile(bar(), (30, 1)) + rng.normal(0, 4, (30, 200))  # a strip of 30 rows: the mean falls with the width
    rising, falling = find_edges(profile(region.clip(0, 255), "x"))
    assert rising.position == pytest.approx(19.5, abs=0.1) and falling.position == pytest.approx(139.5, abs=0.1)


def test_the_profile_is_the_mean_across_the_strip_in_x_or_y():
    region = np.zeros((4, 6), np.uint8)
    region[:, 3:] = 100
    assert profile(region, "x").tolist() == [0, 0, 0, 100, 100, 100] and profile(region, "y").tolist() == [50, 50, 50, 50]
    assert profile(np.stack([region] * 3, axis=2), "x").shape == (6,)  # a colour strip is read in gray


def test_a_ramp_of_gradient_is_scaled_to_the_step():
    step = np.concatenate([np.zeros(50), np.full(50, 100.0)])
    assert gradient(step, 2.0).max() == pytest.approx(100, rel=0.03)


def test_a_sigma_under_half_a_pixel_is_refused():
    with pytest.raises(ValueError):
        find_edges(bar(), sigma=0.2)


# --- an arc: rays from a centre, and the circle through the edges they find (E2) ------------------------

from vision_station.algorithms.calipers import fit_circle, ray_profiles  # noqa: E402


def disc(radius=40.0, centre=(59.5, 59.5), size=(120, 120), low=40.0, high=200.0, inside_light=True):
    """A disc whose edge is area-averaged (a pixel on the edge has the share of the disc it covers)."""
    yy, xx = np.mgrid[: size[0], : size[1]].astype(np.float64)
    share = np.clip(0.5 - (np.hypot(xx - centre[0], yy - centre[1]) - radius), 0, 1)
    values = low + (high - low) * share if inside_light else high - (high - low) * share
    return values.astype(np.float64)


def test_a_ray_reads_the_levels_from_the_centre_outwards():
    image = disc()
    rays = ray_profiles(image, (59.5, 59.5), (0, 59), np.array([0.0, np.pi / 2, np.pi]))
    assert rays.shape == (3, 60)
    assert rays[:, 10].tolist() == pytest.approx([200, 200, 200], abs=0.5) and rays[:, 55].tolist() == pytest.approx([40, 40, 40], abs=0.5)


def test_the_edges_of_the_rays_lie_on_a_circle_of_the_right_radius():
    image = disc(radius=40.0)
    angles = np.linspace(0, 2 * np.pi, 24, endpoint=False)
    rays = ray_profiles(image, (59.5, 59.5), (5, 58), angles)
    radii = [find_edges(r, 1.0, "falling", 20)[0].position + 5 for r in rays]
    assert radii == pytest.approx([40.0] * 24, abs=0.15)


def test_a_circle_is_fitted_to_points_even_off_centre_and_a_false_edge_is_dropped():
    angles = np.linspace(0, 2 * np.pi, 36, endpoint=False)
    points = np.column_stack([30 + 25 * np.cos(angles), 70 + 25 * np.sin(angles)])
    cx, cy, radius, rms, kept = fit_circle(points)
    assert (cx, cy, radius) == pytest.approx((30, 70, 25), abs=1e-6) and rms < 1e-6 and kept.all()
    points[5] = (30 + 40, 70)  # a false edge far outside
    cx, cy, radius, rms, kept = fit_circle(points)
    assert radius == pytest.approx(25, abs=1e-6) and not kept[5] and kept.sum() == 35


def test_points_that_are_no_circle_give_none():
    assert fit_circle(np.array([[0.0, 0.0], [1.0, 1.0]])) is None
    assert fit_circle(np.column_stack([np.arange(10.0), np.arange(10.0) * 2])) is None  # on a line
