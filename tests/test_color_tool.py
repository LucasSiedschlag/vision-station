import numpy as np
import pytest

from vision_station.tools import ToolError, run_tool, tool_types

RED, BLUE, WHITE, GRAY = (30, 30, 220), (200, 90, 30), (255, 255, 255), (128, 128, 128)  # BGR


def patch(color, size=(40, 100)):
    return np.full((*size, 3), color, np.uint8)


def color(region, **params):
    return run_tool("color", 1, region, params)


def test_registered():
    assert ("color", 1) in tool_types()


def test_area_of_a_hue_range_that_wraps_through_red():
    region = patch(WHITE)
    region[:, :70] = RED
    r = color(region, hue=[170, 10], s_min=100, v_min=70, min_fraction=0.5)
    assert r.passed and r.score == 1.0 and r.values["fraction"] == pytest.approx(0.7)
    r = color(region, hue=[170, 10], s_min=100, v_min=70, min_fraction=0.9)
    assert not r.passed and r.score == pytest.approx(0.7 / 0.9)
    assert r.reason("Cor presente em só {fraction:.0%} da área") == "Cor presente em só 70% da área"


def test_other_colors_and_gray_do_not_count():
    assert color(patch(BLUE), hue=[170, 10], s_min=100, min_fraction=0.1).values["fraction"] == 0.0
    # gray has hue 0: a hue range only means something with a saturation limit
    assert color(patch(GRAY), hue=[170, 10], min_fraction=0.1).values["fraction"] == 1.0
    assert color(patch(GRAY), hue=[170, 10], s_min=60, min_fraction=0.1).values["fraction"] == 0.0
    assert color(patch(BLUE), hue=[100, 130], s_min=100, min_fraction=0.9).passed


def test_value_alone_finds_dark_or_white_and_gray_images_work():
    gray = np.full((20, 20), 255, np.uint8)
    gray[:, :5] = 0
    r = color(gray, v_max=50, min_fraction=0.2)
    assert r.passed and r.values["fraction"] == pytest.approx(0.25)


def test_a_darker_picture_still_matches_with_a_low_value_limit():
    dim = (patch(RED).astype(np.float32) * 0.6).astype(np.uint8)
    assert color(dim, hue=[170, 10], s_min=100, v_min=70, min_fraction=0.9).passed
    assert not color(dim, hue=[170, 10], s_min=100, v_min=200, min_fraction=0.9).passed


def test_reference_color_with_a_distance():
    region = patch((40, 40, 210))  # a slightly different red
    assert color(region, mode="reference", rgb=[220, 30, 30], max_distance=20, min_fraction=0.9).passed
    assert not color(patch(BLUE), mode="reference", rgb=[220, 30, 30], max_distance=20, min_fraction=0.1).passed


def test_max_fraction_checks_that_a_color_is_absent():
    region = patch(WHITE)
    assert color(region, hue=[170, 10], s_min=100, max_fraction=0.01).passed
    region[:, :10] = RED
    r = color(region, hue=[170, 10], s_min=100, max_fraction=0.01)
    assert not r.passed and 0 < r.score < 1


def test_coverage_along_the_length_and_the_longest_gap():
    strip = patch(WHITE, size=(20, 200))
    strip[:, :60] = RED
    strip[:, 140:] = RED  # 80 px missing in the middle
    r = color(strip, hue=[170, 10], s_min=100, axis="x", min_coverage=0.9, max_gap=0.1)
    assert not r.passed
    assert r.values["coverage"] == pytest.approx(0.6) and r.values["gap"] == pytest.approx(0.4)
    assert r.details["gap_at"] == pytest.approx([0.3, 0.7])
    assert r.reason("Faixa ausente em {missing:.0%} do comprimento") == "Faixa ausente em 40% do comprimento"
    strip[:, :] = RED
    assert color(strip, hue=[170, 10], s_min=100, axis="x", min_coverage=0.9, max_gap=0.1).passed


def test_a_thin_line_does_not_cover_unless_line_min_allows_it():
    strip = patch(WHITE, size=(20, 100))
    strip[9:11, :] = RED  # 10% of each column
    assert color(strip, hue=[170, 10], s_min=100, axis="x", min_coverage=0.9).values["coverage"] == 0.0
    assert color(strip, hue=[170, 10], s_min=100, axis="x", line_min=0.05, min_coverage=0.9).passed


def test_vertical_axis():
    strip = patch(WHITE, size=(200, 20))
    strip[:100] = RED
    r = color(strip, hue=[170, 10], s_min=100, axis="y", min_coverage=0.4)
    assert r.passed and r.values["coverage"] == pytest.approx(0.5)


def test_empty_region_fails_without_crashing():
    r = color(np.zeros((0, 0, 3), np.uint8), hue=[170, 10], axis="x", min_coverage=0.5, min_fraction=0.1)
    assert not r.passed and r.score == 0.0


@pytest.mark.parametrize(
    "params",
    [
        {"hue": [170, 10]},  # no criterion
        {"min_coverage": 0.5},  # coverage needs an axis
        {"mode": "reference", "min_fraction": 0.5},  # reference needs rgb
        {"s_min": 200, "s_max": 100, "min_fraction": 0.5},
        {"hue": [0, 200], "min_fraction": 0.5},  # OpenCV hue is 0..179
        {"min_fraction": 0.8, "max_fraction": 0.2},
        {"min_fraction": 0.5, "colour": "red"},  # unknown field
    ],
)
def test_invalid_parameters_are_refused(params):
    with pytest.raises(ToolError):
        color(patch(RED), **params)


def test_noise_does_not_break_it():
    rng = np.random.default_rng(1)
    for _ in range(20):
        r = color(rng.integers(0, 256, (30, 50, 3), dtype=np.uint8), hue=[170, 10], s_min=100, axis="x", min_coverage=0.9, max_gap=0.1)
        assert 0.0 <= r.score <= 1.0
