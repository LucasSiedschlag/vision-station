"""The error-code catalog (TD-22, FR-INS-14): documented, used, and on every ERROR."""

import re
from pathlib import Path

import numpy as np

from test_verification import make_bundle, qr_scene
from vision_station.cameras import Frame
from vision_station.core.errors import CATALOG, ErrorCode
from vision_station.core.results import Outcome
from vision_station.pipeline import inspect_job

ROOT = Path(__file__).resolve().parents[1]


def documented_codes() -> set[int]:
    text = (ROOT / "docs" / "architecture.md").read_text(encoding="utf-8")
    section = text[text.index("### 10.3 Result contract") :]
    section = section[: section.index("\n---")]
    codes: set[int] = set()
    for row in re.findall(r"^\| (E\d{3}(?: / E\d{3})*) \|", section, re.M):
        codes |= {int(c[1:]) for c in row.split(" / ")}
    return codes


def test_the_catalog_and_the_table_of_architecture_10_3_are_the_same():
    assert documented_codes() == {int(c) for c in ErrorCode}
    assert set(CATALOG) == set(ErrorCode)


def test_every_code_raised_today_is_used_in_the_code_and_planned_ones_are_not():
    source = "\n".join(p.read_text(encoding="utf-8") for p in (ROOT / "src" / "vision_station").rglob("*.py") if p.name != "errors.py")
    for code, info in CATALOG.items():
        used = f"ErrorCode.{code.name}" in source
        assert used == (not info.planned), f"{code.name}: planned={info.planned!r}, used={used}"


def test_codes_group_by_hundreds():
    groups = {1: "image", 2: "location", 3: "region", 4: "camera", 5: "system", 6: "machine"}
    for code, info in CATALOG.items():
        assert info.group == groups[int(code) // 100]


def test_every_error_of_the_pipeline_has_its_code_and_a_pass_or_fail_has_none():
    bundle = make_bundle(brightness=(50, 200))
    dark = inspect_job(bundle, Frame((qr_scene("LOTE-1") * 0.1).astype(np.uint8), 0.0))
    assert dark.outcome is Outcome.ERROR and dark.error_code == ErrorCode.TOO_DARK
    invalid = inspect_job(bundle, Frame(np.zeros((0, 0), np.uint8), 0.0))
    assert invalid.error_code == ErrorCode.INVALID_IMAGE and invalid.reason == "Imagem inválida da câmera"
    ok = inspect_job(make_bundle(), Frame(qr_scene("LOTE-1"), 0.0))
    assert ok.outcome is Outcome.PASS and ok.error_code == 0
