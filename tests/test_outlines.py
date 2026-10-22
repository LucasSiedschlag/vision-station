"""The outlines of a mask for the marks of `color` and `blob` (VIA-0124): bounded in cost and in size, deterministic."""

import time

import numpy as np

from vision_station.algorithms.outlines import MAX_SIDE, mask_outlines
from vision_station.core.results import MAX_MARK_POINTS


def test_a_blob_is_outlined_in_the_pixels_of_the_mask():
    mask = np.zeros((100, 200), bool)
    mask[20:60, 30:90] = True
    (outline,) = mask_outlines(mask)
    xs, ys = [p[0] for p in outline], [p[1] for p in outline]
    assert (min(xs), min(ys), max(xs), max(ys)) == (30, 20, 89, 59)


def test_the_largest_come_first_and_there_are_at_most_so_many():
    mask = np.zeros((100, 300), bool)
    mask[10:20, 10:20] = True  # 100 px
    mask[10:50, 100:150] = True  # 2000 px
    mask[10:30, 200:230] = True  # 600 px
    first = mask_outlines(mask)
    assert [round(min(p[0] for p in o)) for o in first] == [100, 200, 10]
    assert len(mask_outlines(mask, most=2)) == 2


def test_a_dot_has_no_outline_and_a_thin_line_has_two_points_even_on_a_large_mask():
    assert mask_outlines(np.zeros((50, 50), bool)) == []
    dot = np.zeros((50, 50), bool)
    dot[10, 10] = True
    assert mask_outlines(dot) == []
    line = np.zeros((2000, 2000), bool)
    line[1000, 100:1900] = True  # larger than MAX_SIDE: reduced, and the line stays
    (outline,) = mask_outlines(line)
    assert len(outline) == 2 and abs(outline[0][0] - 100) < 4 and abs(outline[1][0] - 1899) < 4


def test_a_noisy_outline_is_simplified_to_the_cap_and_never_cut():
    rng = np.random.default_rng(1)
    mask = np.zeros((400, 400), bool)
    mask[50:350, 50:350] = True
    mask[50:350, 50:350] &= rng.random((300, 300)) > 0.02  # a ragged edge keeps the outer outline long
    (outline,) = mask_outlines(mask)
    assert 3 <= len(outline) <= MAX_MARK_POINTS


def test_a_large_mask_is_scaled_back_and_deterministic():
    mask = np.zeros((3000, 2000), bool)
    mask[600:2400, 400:1600] = True
    a, b = mask_outlines(mask), mask_outlines(mask)
    assert a == b
    xs, ys = [p[0] for p in a[0]], [p[1] for p in a[0]]
    step = max(mask.shape) / MAX_SIDE  # the precision is a pixel of the reduced mask
    assert all(abs(got - want) <= step * 1.2 for got, want in ((min(xs), 400), (max(xs), 1600), (min(ys), 600), (max(ys), 2400)))
    assert max(mask.shape) > MAX_SIDE


def test_a_speckled_four_megapixel_mask_costs_little():
    rng = np.random.default_rng(0)
    mask = rng.random((2000, 2000)) > 0.5
    started = time.perf_counter()
    assert len(mask_outlines(mask)) <= 16
    assert time.perf_counter() - started < 0.5  # 17 ms here; the bound only catches a contour for every speck (300 ms)
