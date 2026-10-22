"""The compare tool: what it refuses, what it reports and how it reads the model (VIA-0075 CP1)."""

import cv2
import numpy as np
import pytest

from test_variation import GOOD, defect, sample
from vision_station.algorithms.variation import teach
from vision_station.core.jobfiles import JobFileError
from vision_station.tools import ToolError, run_tool

FILES = {"models/m.var": teach(GOOD)}


def compare(region, files=FILES, **params):
    return run_tool("compare", 1, region, {"model": "models/m.var", "max_area": 30, **params}, files)


def test_a_region_of_the_wrong_size_is_refused_not_judged():
    with pytest.raises(ToolError, match="taught on 160x120"):
        compare(cv2.resize(sample(1), (80, 60)))
    with pytest.raises(ToolError, match="empty"):
        compare(np.zeros((0, 0), np.uint8))


def test_a_model_that_is_missing_damaged_or_not_a_model_is_refused():
    with pytest.raises(JobFileError):
        compare(sample(1), files={})
    damaged = bytearray(FILES["models/m.var"])
    damaged[-5] ^= 0xFF
    with pytest.raises(ToolError, match="damaged|model"):
        compare(sample(1), files={"models/m.var": bytes(damaged)})
    with pytest.raises(ToolError, match="not a variation model"):
        compare(sample(1), files={"models/m.var": b"onnx..."})


def test_the_gain_the_defects_and_the_shift_are_reported():
    result = compare(defect(sample(2), x=50, y=30), max_area=1000)
    assert result.passed and result.values["count"] == 1 and result.details["gain"][0] == pytest.approx(1.0, abs=0.02)
    assert result.reason("{count} defeito de {area:.0f} px²") .startswith("1 defeito de 14")


def test_the_marks_of_a_region_that_was_resized_come_back_in_its_own_pixels():
    larger = cv2.resize(defect(sample(3), x=50, y=30), (176, 132), interpolation=cv2.INTER_LINEAR)  # 10 % larger
    result = compare(larger, max_area=0)
    xs = [p[0] for m in result.marks for p in m.points]
    assert not result.passed and 50 * 1.1 - 3 <= min(xs) and max(xs) <= 62 * 1.1 + 3 and result.marks[0].role == "defect"


def test_a_model_is_cached_by_its_bytes():
    from vision_station.algorithms import variation

    variation.load.cache_clear()
    compare(sample(4)), compare(sample(5))
    assert variation.load.cache_info().hits >= 1
