"""The OR between tools on a taped box (TD-33, VIA-0139): a logo or a text block on the tape is enough, a bare tape or no box is never a PASS."""

import cv2
import numpy as np
import pytest
import yaml

from test_verification import FIXTURES, png
from vision_station.cameras import Frame
from vision_station.core.results import Outcome
from vision_station.jobs import CameraProfile, Job
from vision_station.pipeline import inspect_job
from vision_station.store import JobBundle
from vision_station.verification import make_reference_files

FILM = 225  # a light film over the cardboard
H, W = 300, 700
BAND = (110, 190)  # the rows of the horizontal tape


def logo():
    img = np.full((30, 70), FILM, np.uint8)
    cv2.putText(img, "VS-9", (4, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.7, 40, 2)
    img[26:29, 4:66] = 40
    return img


def text_block():
    img = np.full((24, 110), FILM, np.uint8)
    cv2.putText(img, "FRAGIL", (4, 18), cv2.FONT_HERSHEY_DUPLEX, 0.6, 40, 1)
    return img


FILES = {"patterns/logo.png": png(logo()), "patterns/text.png": png(text_block())}


def scene(logos=(), texts=(), tape=True, box=True):
    """A cardboard box on a dark table; a tape across it with a logo at each x in `logos` and a text block at each x in `texts`."""
    img = np.full((H, W), 60, np.uint8)  # the table
    rng = np.random.default_rng(5)
    if box:
        img[20:280, 20:680] = (150 + rng.integers(-6, 7, (260, 660))).astype(np.uint8)  # the cardboard, a little grain
        if tape:
            img[BAND[0] : BAND[1], 20:680] = FILM
            for x in logos:
                img[125:155, x : x + 70] = logo()
            for x in texts:
                img[128:152, x : x + 110] = text_block()
    return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)


def bundle(grouped=True):
    data = yaml.safe_load((FIXTURES / "job.yaml").read_text(encoding="utf-8"))
    data["quality"] = {"brightness": {"min": 30, "max": 250}, "sharpness_min_ratio": 0.3}
    data["geometry"] = {"rois": {"tape": {"relative_to": "frame", "rect": [0.03, BAND[0] / H, 0.97, BAND[1] / H]}}}
    member = {"type": "pattern", "version": 2, "roi": "tape"}
    data["tools"] = [
        {**member, "id": "logo", "params": {"template": "patterns/logo.png", "min_count": 1}, "reason_fail": "Sem logo", **({"group": "marca"} if grouped else {})},
        {**member, "id": "texto", "params": {"template": "patterns/text.png", "min_count": 1}, "reason_fail": "Sem texto", **({"group": "marca"} if grouped else {})},
    ]
    if grouped:
        data["groups"] = {"marca": {"reason_fail": {"pt-BR": "Fita sem logo nem texto", "en": "Tape with no logo or text"}}}
    profile = CameraProfile.model_validate(yaml.safe_load((FIXTURES / "profile.yaml").read_text()))
    return JobBundle(Job.model_validate(data), profile, {**make_reference_files(scene([100], [300])), **FILES})


def run(img, **kw):
    return inspect_job(bundle(**kw), Frame(img, 0.0))


@pytest.mark.parametrize(
    "logos, texts",
    [
        ((100,), ()),  # only a logo
        ((), (300,)),  # only a text block
        ((100, 400), (250,)),  # two logos and a text block
        ((100,), (250, 450)),  # a logo and two text blocks
        ((100, 250, 400, 550), ()),  # four logos
    ],
)
def test_the_tape_passes_with_a_logo_or_a_text_block_whatever_the_count(logos, texts):
    r = run(scene(logos, texts))
    assert r.outcome is Outcome.PASS and r.reason == ""
    assert [(g.id, g.passed) for g in r.groups] == [("marca", True)]


def test_a_bare_tape_fails_with_the_text_of_the_group():
    r = run(scene())
    assert r.outcome is Outcome.FAIL and r.reason == "Fita sem logo nem texto"
    assert {c.tool for c in r.reason_codes} == {"logo", "texto"}


def test_a_box_without_tape_fails():
    assert run(scene(tape=False)).outcome is Outcome.FAIL


@pytest.mark.parametrize("img", [scene(box=False), np.full((H, W, 3), 60, np.uint8), np.zeros((H, W, 3), np.uint8)])
def test_a_background_without_a_box_is_never_a_pass(img):
    assert run(img).outcome is not Outcome.PASS


@pytest.mark.parametrize("seed", range(10))
def test_noise_is_never_a_pass(seed):
    noise = np.random.default_rng(seed).integers(0, 256, (H, W, 3), dtype=np.uint8)
    assert run(noise).outcome is not Outcome.PASS


def test_without_the_group_the_same_tape_needs_both():
    """The OR is what accepts a tape with only one of the two; with no group both are required."""
    only_logo = scene([100], ())
    assert run(only_logo).outcome is Outcome.PASS
    r = run(only_logo, grouped=False)
    assert r.outcome is Outcome.FAIL and r.reason == "Sem texto"
