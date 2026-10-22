"""The brightness tool: what it measures, how far it is from failing, and what a job text can say (VIA-0075 B1)."""

import numpy as np
import pytest

from vision_station.tools import ToolError, run_tool


def run(region, **params):
    return run_tool("brightness", 1, region, params)


def test_it_measures_a_color_region_in_gray():
    blue = np.full((20, 20, 3), (200, 90, 30), np.uint8)  # BGR; gray = 0.114 B + 0.587 G + 0.299 R
    result = run(blue, min_mean=0)
    assert result.values["mean"] == pytest.approx(0.114 * 200 + 0.587 * 90 + 0.299 * 30, abs=1)


def test_the_score_falls_with_the_miss_and_is_one_exactly_when_it_passes():
    dark = np.full((20, 20), 50, np.uint8)
    assert run(dark, min_mean=100).score == pytest.approx(0.5)  # half of what was asked
    bright = np.full((20, 20), 230, np.uint8)
    over = run(bright, max_mean=200)
    assert not over.passed and 0 < over.score < 1  # past the limit, towards 255
    assert run(np.full((20, 20), 200, np.uint8), max_mean=200).score == 1.0


def test_every_criterion_that_is_given_must_hold_and_the_failing_ones_are_named():
    region = np.zeros((10, 10), np.uint8)
    region[:5] = 250
    result = run(region, min_mean=200, max_std=50, level=200, max_above=0.4)
    failed = sorted(c.code for c in result.criteria if not c.passed)
    assert failed == ["max_above", "max_std", "min_mean"]
    assert result.reason("{above:.0%} acima de {level}, variação {std:.0f}") == "50% acima de 200, variação 125"


def test_the_level_itself_is_in_neither_share():
    region = np.full((10, 10), 128, np.uint8)
    result = run(region, level=128, max_above=0.0, max_below=0.0)
    assert result.passed and result.values["above"] == 0 and result.values["below"] == 0


def test_an_empty_region_is_refused_not_passed():
    with pytest.raises(ToolError):
        run(np.zeros((0, 5), np.uint8), min_mean=1)
