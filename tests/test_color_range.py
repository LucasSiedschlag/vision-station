"""A color range proposed from sampled pixels (FR-UI-13, document 05 §19.4)."""

import cv2
import numpy as np
import pytest

from test_api import env, login  # noqa: F401
from test_manage_api import b64, mnt  # noqa: F401
from vision_station.algorithms.color import ColorRange, color_mask
from vision_station.algorithms.color_range import propose_range
from test_verification import png


def patch(h: int, s: int, v: int, spread: int = 0, n: int = 40, seed: int = 1) -> np.ndarray:
    """An n×n BGR patch whose HSV is (h, s, v) with a spread of +-`spread` in each channel."""
    rng = np.random.default_rng(seed)
    hsv = np.empty((n, n, 3), np.int16)
    hsv[..., 0] = (h + rng.integers(-spread, spread + 1, (n, n))) % 180
    hsv[..., 1] = np.clip(s + rng.integers(-spread, spread + 1, (n, n)) * 4, 0, 255)
    hsv[..., 2] = np.clip(v + rng.integers(-spread, spread + 1, (n, n)) * 4, 0, 255)
    return cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)


def test_a_blue_is_a_band_around_its_hue_and_it_contains_what_was_sampled():
    found = propose_range([patch(110, 200, 180, spread=4)])
    assert found.hue is not None and found.hue[0] <= 106 and found.hue[1] >= 114 and found.hue[0] < found.hue[1]
    assert found.kept >= 0.95 and found.leak is None and found.pixels == 1600


def test_a_red_that_spans_the_wrap_is_one_band_through_zero():
    reds = [patch(174, 220, 200, spread=0, seed=2), patch(4, 220, 200, spread=0, seed=3)]
    found = propose_range(reds)
    assert found.hue is not None and found.hue[0] > found.hue[1]  # 170-ish .. 10-ish, not the whole circle
    lo, hi = found.hue
    assert 165 <= lo <= 176 and 2 <= hi <= 14
    mask = color_mask(np.concatenate(reds, axis=1), ColorRange(hue=found.hue, s_min=found.s_min, s_max=found.s_max, v_min=found.v_min, v_max=found.v_max))
    assert mask.mean() > 0.95


def test_grays_and_whites_have_no_hue_to_keep():
    found = propose_range([patch(0, 8, 220, spread=2)])
    assert found.hue is None and found.v_min > 150 and found.s_max < 60


def test_a_flat_patch_still_gets_a_band_wide_enough_to_use():
    """One colour, no spread (a click on a flat area): the percentiles collapse to a point, which no camera would hit twice."""
    found = propose_range([patch(110, 150, 190, spread=0)])
    lo, hi = found.hue
    assert hi - lo >= 8 and lo < 110 < hi
    assert found.s_max - found.s_min >= 40 and found.v_max - found.v_min >= 40
    assert found.s_min < 150 < found.s_max and found.v_min < 190 <= found.v_max
    wrapped = propose_range([patch(0, 200, 200, spread=0)])  # a flat red: the band opens on both sides of zero
    assert wrapped.hue[0] > wrapped.hue[1]


def test_the_stray_pixels_do_not_widen_the_band():
    cap = patch(110, 200, 180, spread=2)
    cap[:2, :2] = cv2.cvtColor(np.uint8([[[30, 200, 180]]]), cv2.COLOR_HSV2BGR)  # a few yellow pixels
    found = propose_range([cap])
    assert found.hue is not None and found.hue[1] - found.hue[0] < 20


def test_the_label_next_to_the_cap_is_left_out():
    """A blue cap and a lighter, paler blue label: the range is tightened until the label is out and the cap stays."""
    cap = patch(110, 150, 190, spread=14)  # a shaded cap: a wide band of saturation and value
    label = patch(108, 100, 240, spread=3, seed=5)
    loose = propose_range([cap])
    assert loose.hue is not None
    assert color_mask(label, ColorRange(hue=loose.hue, s_min=loose.s_min, s_max=loose.s_max, v_min=loose.v_min, v_max=loose.v_max)).mean() > 0.5  # it would catch the label
    found = propose_range([cap], [label])
    assert found.leak is not None and found.leak <= 0.02
    assert found.kept >= 0.7


def test_too_few_pixels_propose_nothing():
    assert propose_range([patch(110, 200, 180, n=3)]) is None
    assert propose_range([]) is None


def test_the_route_proposes_from_crops_and_refuses_bad_input(env, mnt):  # noqa: F811
    crop = png(patch(110, 200, 180, spread=3))
    body = {"include": [b64(crop)]}
    out = env.client.post("/api/editor/suggest/colour", headers=mnt, json=body)
    assert out.status_code == 200
    out = out.json()
    assert out["ok"] and out["hue"][0] < out["hue"][1] and out["kept"] > 0.9
    assert env.client.post("/api/editor/suggest/colour", json=body).status_code == 401
    assert env.client.post("/api/editor/suggest/colour", headers=mnt, json={"include": ["not base64!"]}).json()["ok"] is False
    tiny = env.client.post("/api/editor/suggest/colour", headers=mnt, json={"include": [b64(png(patch(110, 200, 180, n=2)))]}).json()
    assert tiny["ok"] is False and tiny["message"]
