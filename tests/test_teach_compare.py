"""Teaching `compare` from pictures of good parts and then inspecting with it (VIA-0075 CP1)."""

import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from test_fixtures_pipeline import H, W, job, part_scene, run
from validation import perturb
from vision_station.algorithms import variation
from vision_station.core.results import Outcome
from vision_station.jobs import Job
from vision_station.pipeline.teach import teach_tool
from vision_station.store import JobBundle

TOOL = {"id": "cmp", "type": "compare", "version": 1, "roi": "anchor", "params": {"model": "models/m.var", "max_area": 200}, "reason_fail": "Peça diferente"}


def good_parts(n=15):
    """Good parts as they arrive: a little turned, a little larger or smaller, a little off the centre, with the noise of a sensor."""
    rng = np.random.default_rng(11)
    out = []
    for i in range(n):
        scene = part_scene(angle=float(rng.uniform(-6, 6)), scale=float(rng.uniform(0.96, 1.04)), at=(320.0 + float(rng.uniform(-8, 8)), 240.0 + float(rng.uniform(-6, 6))))
        out.append((f"good{i:02d}.png", perturb.noise(scene, seed=i)))
    return out


def with_model(data: bytes | None) -> JobBundle:
    bundle = job(tools=[TOOL])
    return JobBundle(bundle.job, bundle.profile, {**bundle.extra, **({"models/m.var": data} if data else {})})


def test_a_model_is_taught_from_the_regions_the_fixture_cut_upright():
    taught = teach_tool(with_model(None), "cmp", good_parts())
    assert taught.used == 15 and taught.skipped == () and taught.size == pytest.approx((160, 90), abs=2)
    model = variation.load(taught.data)
    assert model.count == 15 and model.size == taught.size and model.channels == 3


def test_a_part_turned_and_scaled_is_judged_as_a_good_one_and_a_part_without_its_cap_is_not():
    bundle = with_model(teach_tool(with_model(None), "cmp", good_parts()).data)
    good = run(bundle, perturb.noise(part_scene(angle=-4.0, scale=1.03, at=(326.0, 236.0)), seed=99))
    assert good.outcome is Outcome.PASS, good.reason
    bad = run(bundle, perturb.noise(part_scene(angle=3.0, cap=False), seed=98))
    assert bad.outcome is Outcome.FAIL and bad.tools[0].values["area"] > 200
    assert any(m.role == "defect" for m in bad.tools[0].marks)


def test_a_picture_that_cannot_be_used_is_listed_with_its_reason_never_dropped_in_silence():
    pictures = good_parts(5) + [("empty.png", np.full((H, W, 3), (205, 205, 200), np.uint8))]
    taught = teach_tool(with_model(None), "cmp", pictures)
    assert taught.used == 5 and [s.name for s in taught.skipped] == ["empty.png"] and taught.skipped[0].reason


def test_too_few_usable_pictures_or_an_unknown_tool_is_refused_with_the_count():
    with pytest.raises(ValueError, match="only 2 of 3 pictures.*at least 3"):
        teach_tool(with_model(None), "cmp", good_parts(2) + [("empty.png", np.full((H, W, 3), (205, 205, 200), np.uint8))])
    with pytest.raises(ValueError, match="no tool 'nope'"):
        teach_tool(with_model(None), "nope", good_parts(3))


def test_the_script_runs_and_says_how_to_use_it():
    script = Path(__file__).resolve().parents[1] / "scripts" / "teach_compare.py"
    done = subprocess.run([sys.executable, str(script), "--help"], capture_output=True, text=True, timeout=120)
    assert done.returncode == 0 and "PICTURES_FOLDER" in done.stdout
