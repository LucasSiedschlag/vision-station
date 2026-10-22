"""V4: the same outcome under brightness +-15 %, Gaussian noise of 2 gray levels and a small shift; a locator also
follows the part, and one that gives a pose follows a turn (architecture §15.3, NFR-ACC-5)."""

import pytest

from validation import perturb
from validation.registry import case_for, entries
from vision_station.locators import run_locator
from vision_station.tools import run_tool

TOLERANCE = 0.01  # of the frame: where a locator may be off, fractions
TURN_TOLERANCE = 2.0  # degrees


def _disturbed(image):
    yield "darker", perturb.brightness(image, perturb.BRIGHTNESS[0])
    yield "brighter", perturb.brightness(image, perturb.BRIGHTNESS[1])
    yield "noise", perturb.noise(image)
    yield "shift", perturb.shift(image, *perturb.SHIFT_PX)


@pytest.mark.parametrize("kind,name,version", [p for p in entries("V4") if p.values[0] == "tool"])
def test_a_tool_keeps_its_outcome_under_light_noise_and_a_shift(kind, name, version):
    case = case_for(kind, name, version)
    for label, region in (("passing", case.passing), ("failing", case.failing)):
        expected = run_tool(name, version, region, case.params, case.files).passed
        for how, image in _disturbed(region):
            assert run_tool(name, version, image, case.params, case.files).passed == expected, f"{label} region, {how}"


def _found(name, version, case, frame):
    fixture = run_locator(name, version, frame, case.params, case.files)
    assert fixture is not None, "the part was not found"
    return fixture


def _near(rect, expected, tolerance=TOLERANCE):
    return all(abs(a - b) <= tolerance for a, b in zip(rect, expected))


@pytest.mark.parametrize("kind,name,version", [p for p in entries("V4") if p.values[0] == "locator"])
def test_a_locator_finds_the_part_under_light_noise_and_a_shift(kind, name, version):
    case = case_for(kind, name, version)
    scene = case.scene
    h, w = scene.frame.shape[:2]
    assert _near(_found(name, version, case, scene.frame).rect, scene.rect), "the case's own picture"
    for how, image in _disturbed(scene.frame):
        expected = scene.rect
        if how == "shift" and scene.follows:
            dx, dy = perturb.SHIFT_PX
            expected = (expected[0] + dx / w, expected[1] + dy / h, expected[2] + dx / w, expected[3] + dy / h)
        assert _near(_found(name, version, case, image).rect, expected), how


@pytest.mark.parametrize("kind,name,version", entries("V4.rotation"))
def test_a_locator_follows_a_turn_with_a_pose(kind, name, version):
    case = case_for(kind, name, version)
    if not case.scene.follows:
        pytest.skip("it does not look at the picture")
    fixture = _found(name, version, case, perturb.turn(case.scene.frame, perturb.TURN_DEGREES))
    assert fixture.angle == pytest.approx(perturb.TURN_DEGREES, abs=TURN_TOLERANCE)
    x0, y0, x1, y1 = case.scene.rect
    cx, cy = fixture.centre
    assert abs(cx - (x0 + x1) / 2) <= TOLERANCE and abs(cy - (y0 + y1) / 2) <= TOLERANCE
