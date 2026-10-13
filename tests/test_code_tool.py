from pathlib import Path

import cv2
import numpy as np
import pytest
import zxingcpp
import yaml

from vision_station.jobs import Job
from vision_station.tools import ToolError, check_job_tools, get_tool, run_tool, tool_types

FIXTURES = Path(__file__).parent / "fixtures"
QR = zxingcpp.BarcodeFormat.QRCode
CODE128 = zxingcpp.BarcodeFormat.Code128
DATAMATRIX = zxingcpp.BarcodeFormat.DataMatrix
EAN13 = zxingcpp.BarcodeFormat.EAN13


def make(text, fmt=QR, scale=4):
    """A code as a BGR image on a white background."""
    gray = np.array(zxingcpp.create_barcode(text, fmt).to_image(scale=scale))
    return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)


def on_canvas(code, size=(800, 800), angle=0.0, at=(100, 100)):
    canvas = np.full((*size, 3), 255, np.uint8)
    y, x = at
    canvas[y : y + code.shape[0], x : x + code.shape[1]] = code
    if angle:
        m = cv2.getRotationMatrix2D((size[1] / 2, size[0] / 2), angle, 1.0)
        canvas = cv2.warpAffine(canvas, m, (size[1], size[0]), borderValue=(255, 255, 255))
    return canvas


def read(image, **params):
    return run_tool("code", 1, image, params)


@pytest.mark.parametrize("fmt, text", [(QR, "LOTE-2026-10"), (CODE128, "ABC-12345"), (DATAMATRIX, "DM 77"), (EAN13, "5901234123457")])
def test_reads_each_kind_of_code(fmt, text):
    result = read(on_canvas(make(text, fmt)))
    assert result.passed and result.score == 1.0
    assert result.details["codes"][0]["text"] == text
    assert result.details["codes"][0]["format"] == fmt.name


@pytest.mark.parametrize("angle", [0, 30, 90, 180, 270])
def test_reads_rotated_codes(angle):
    result = read(on_canvas(make("ROT-1"), angle=angle))
    assert result.passed and result.values["texts"] == "ROT-1"


def test_reads_with_noise_blur_and_low_contrast():
    img = on_canvas(make("NOISY-7", scale=5))
    img = cv2.GaussianBlur(img, (5, 5), 1.2)
    img = (img.astype(np.float32) * 0.5 + 100).astype(np.uint8)  # gray on gray
    noise = np.random.default_rng(1).normal(0, 8, img.shape)
    img = np.clip(img + noise, 0, 255).astype(np.uint8)
    assert read(img).passed


def test_reads_light_on_dark_and_grayscale():
    img = 255 - on_canvas(make("INV-3"))
    assert read(img).passed
    assert read(cv2.cvtColor(on_canvas(make("GRAY-3")), cv2.COLOR_BGR2GRAY)).passed
    assert not read(img, try_invert=False).passed


def test_empty_blurred_or_blank_regions_fail_without_crashing():
    blank = np.full((200, 300, 3), 255, np.uint8)
    result = read(blank)
    assert not result.passed and result.score == 0.0 and result.values["found"] == 0
    assert not read(np.zeros((0, 0, 3), np.uint8)).passed
    smeared = cv2.GaussianBlur(on_canvas(make("GONE")), (51, 51), 20)
    assert not read(smeared).passed


def test_expected_text_and_pattern():
    img = on_canvas(make("LOTE-2026-10"))
    assert read(img, expect="LOTE-2026-10").passed
    wrong = read(img, expect="LOTE-2026-11")
    assert not wrong.passed and wrong.values["found"] == 1 and wrong.values["matching"] == 0
    assert read(img, pattern=r"LOTE-\d{4}-\d{2}").passed
    assert not read(img, pattern=r"LOTE-\d{2}").passed  # fullmatch, not a prefix
    assert read(img, expect="OTHER", pattern=r"LOTE-.*").passed  # either one accepts


def test_counts():
    one = make("A-1")
    two = on_canvas(np.vstack([one, np.full((20, one.shape[1], 3), 255, np.uint8), make("B-2")]))
    assert read(two).values["found"] == 2
    assert read(two, min_count=2).passed
    assert not read(on_canvas(one), min_count=2).passed
    partial = read(on_canvas(one), min_count=2)
    assert partial.score == 0.5
    too_many = read(two, max_count=1)
    assert not too_many.passed and too_many.score == 0.0
    assert read(two, expect="A-1", max_count=1).passed  # only accepted codes count


def test_format_filter():
    img = on_canvas(make("ONLY-QR"))
    assert read(img, formats=["QRCode"]).passed
    assert not read(img, formats=["Code128", "EAN13"]).passed


def test_position_is_in_region_coordinates():
    result = read(on_canvas(make("POS"), at=(100, 100)))
    xs = [x for x, _ in result.details["codes"][0]["position"]]
    ys = [y for _, y in result.details["codes"][0]["position"]]
    assert 90 <= min(xs) < max(xs) <= 260 and 90 <= min(ys) < max(ys) <= 260


def test_reason_text_uses_the_values_and_survives_typos():
    result = read(np.full((100, 100, 3), 255, np.uint8), expect="X")
    assert result.reason("Código não lido ({found} encontrados)") == "Código não lido (0 encontrados)"
    assert result.reason("Código {nope}") == "Código {nope}"


@pytest.mark.parametrize(
    "params",
    [{"formats": ["Nope"]}, {"pattern": "("}, {"min_count": 0}, {"min_count": 3, "max_count": 2}, {"surprise": 1}],
)
def test_invalid_parameters_are_refused(params):
    with pytest.raises(ToolError, match="invalid parameters"):
        run_tool("code", 1, np.zeros((10, 10, 3), np.uint8), params)


def test_registry_refuses_unknown_tools_and_versions():
    assert ("code", 1) in tool_types()
    assert get_tool("code", 1).name == "code"
    with pytest.raises(ToolError, match="unknown tool 'nope'"):
        get_tool("nope", 1)
    with pytest.raises(ToolError, match=r"version 2 is not supported \(supported: \[1\]\)"):
        get_tool("code", 2)


def test_job_with_a_code_tool_is_checked_against_the_registry():
    data = yaml.safe_load((FIXTURES / "job.yaml").read_text(encoding="utf-8"))
    data["geometry"] = {"rois": {"label": {"relative_to": "frame", "rect": [0.2, 0.2, 0.8, 0.5]}}}
    data["tools"] = [
        {"id": "lote", "type": "code", "version": 1, "roi": "label", "params": {"formats": ["QRCode"], "pattern": r"LOTE-\d+"}, "reason_fail": "Código não lido"}
    ]
    job = Job.model_validate(data)
    check_job_tools(job)
    data["tools"][0]["params"]["formats"] = ["Nope"]
    with pytest.raises(ToolError, match="tool 'lote'"):
        check_job_tools(Job.model_validate(data))
    data["tools"][0]["version"] = 9
    with pytest.raises(ToolError, match="tool 'lote'"):
        check_job_tools(Job.model_validate(data))
