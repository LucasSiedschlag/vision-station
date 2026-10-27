"""scripts/setup_bench.py prepares the bench: its job must be one the station can run, with a reference image and a reference set
(design rule 4, VIA-0090); the station verifies it again every time it prepares."""

import importlib.util
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest
import zxingcpp

from vision_station.cameras import ApplyReport, Frame
from vision_station.pipeline import inspect_job
from vision_station.store import JobStore
from vision_station.system import load_config
from vision_station.verification import JobVerifier

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "setup_bench.py"


def _script():
    spec = importlib.util.spec_from_file_location("setup_bench", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["setup_bench"] = module
    spec.loader.exec_module(module)
    return module


def _picture(code: str | None) -> np.ndarray:
    image = np.full((540, 960, 3), 170, np.uint8)
    if code:
        qr = np.array(zxingcpp.create_barcode(code, zxingcpp.BarcodeFormat.QRCode).to_image(scale=8))
        image[100 : 100 + qr.shape[0], 100 : 100 + qr.shape[1]] = qr[..., None]
    return image


class _Camera:
    """What the station's verifier asks of the acquisition: an applied profile and a frame."""

    last_apply = ApplyReport(status={})
    applied_serial = profile_serial = 0

    def latest(self):
        return Frame(_picture("BENCH-1"), 0.0)


def _run(tmp_path: Path, *extra: str) -> int:
    pictures = tmp_path / "pictures"
    pictures.mkdir(exist_ok=True)
    cv2.imwrite(str(pictures / "a.png"), _picture("BENCH-1"))
    return _script().main(["--folder", str(pictures), "--data", str(tmp_path / "data"), *extra])


def test_the_bench_job_has_a_reference_and_the_station_verifies_it(tmp_path):
    assert _run(tmp_path) == 0
    store = JobStore(tmp_path / "data")
    ref = store.get_active()
    assert ref is not None
    bundle = store.load(ref)
    assert "reference/reference.png" in bundle.extra and "tests/expected.yaml" in bundle.extra
    assert JobVerifier(inspect_job)(bundle, _Camera()).ok  # the check the station does at every start
    assert load_config(tmp_path / "data").camera.driver == "file"


def test_a_reference_without_a_readable_code_is_refused_and_nothing_is_activated(tmp_path, capsys):
    blank = tmp_path / "blank.png"
    cv2.imwrite(str(blank), _picture(None))
    assert _run(tmp_path, "--reference", str(blank)) == 1
    assert JobStore(tmp_path / "data").get_active() is None
    assert "not activated" in capsys.readouterr().err  # the person at the bench is told why


def test_a_camera_needs_a_reference_image_given(tmp_path, capsys):
    with pytest.raises(SystemExit):
        _script().main(["--name", "C920", "--data", str(tmp_path / "data")])
