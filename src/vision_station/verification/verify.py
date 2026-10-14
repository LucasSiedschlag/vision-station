"""Verification of a job: does it still see and decide as it did when it was saved? (FR-JOB-9, §7.3)

Two parts that catch different problems:
- camera and view: settings not applied, camera moved, lens out of focus, lighting changed.
  Needs the live camera and the reference image.
- decision logic: another software version, model or machine giving different results.
  Needs only the stored reference set, no camera.

The pure functions here take what they need as arguments; `live.py` connects them to the camera.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Literal

import numpy as np

from vision_station.cameras import ApplyReport, Frame, SettingStatus
from vision_station.results import InspectionResult, Outcome
from vision_station.store import JobBundle
from vision_station.verification import metrics
from vision_station.verification.reference import (
    EXPECTED_FILE,
    REFERENCE_IMAGE,
    REFERENCE_META,
    decode_image,
    parse_expected,
    parse_meta,
)

Inspector = Callable[[JobBundle, Frame], InspectionResult]
Locator = Callable[[np.ndarray], tuple[float, float] | None]


@dataclass(frozen=True)
class Check:
    name: str
    passed: bool
    message: str  # Portuguese, for the screen


@dataclass(frozen=True)
class VerificationReport:
    camera_view: tuple[Check, ...] = ()
    decision: tuple[Check, ...] = ()
    warnings: tuple[str, ...] = field(default_factory=tuple)

    @property
    def ok(self) -> bool:
        return all(c.passed for c in (*self.camera_view, *self.decision))

    def failures(self) -> list[Check]:
        return [c for c in (*self.camera_view, *self.decision) if not c.passed]

    def summary(self) -> str:
        if self.ok:
            return "Job verificado"
        return "; ".join(c.message for c in self.failures())


def check_camera_and_view(
    bundle: JobBundle,
    apply_report: ApplyReport | None,
    frame: Frame | None,
    locate: Locator | None = None,
) -> tuple[list[Check], list[str]]:
    """Steps 1 to 4: settings applied, a live frame, and the frame compared with the reference."""
    checks: list[Check] = []
    warnings: list[str] = []

    if apply_report is None:
        checks.append(Check("settings", False, "ajustes da câmera não aplicados"))
    else:
        rejected = sorted(k for k, s in apply_report.status.items() if s is SettingStatus.REJECTED)
        if rejected:
            detail = "; ".join(f"{k}: {apply_report.detail.get(k, 'recusado')}" for k in rejected)
            checks.append(Check("settings", False, f"ajuste não aplicado ({detail})"))
        else:
            checks.append(Check("settings", True, "ajustes da câmera aplicados"))
        warnings += [f"{k}: {apply_report.detail.get(k, 'não suportado')}" for k, s in sorted(apply_report.status.items()) if s is SettingStatus.NOT_SUPPORTED]

    if frame is None:
        checks.append(Check("frame", False, "sem imagem da câmera"))
        return checks, warnings
    checks.append(Check("frame", True, "imagem recebida"))

    q = bundle.job.quality
    bright = metrics.brightness(frame.image)
    in_range = q.brightness.min <= bright <= q.brightness.max
    checks.append(Check("brightness", in_range, f"brilho {bright:.0f} (esperado {q.brightness.min:g} a {q.brightness.max:g})" if not in_range else f"brilho {bright:.0f}"))

    ref_png = bundle.extra.get(REFERENCE_IMAGE)
    ref_image = decode_image(ref_png) if ref_png else None
    if ref_image is None:
        warnings.append("job sem imagem de referência: nitidez, semelhança e posição não conferidas")
        return checks, warnings

    meta = parse_meta(bundle.extra[REFERENCE_META]) if REFERENCE_META in bundle.extra else None
    ref_sharp = meta.sharpness if meta else metrics.sharpness(ref_image)
    sharp = metrics.sharpness(frame.image)
    ratio = sharp / ref_sharp if ref_sharp > 0 else 1.0
    checks.append(Check("sharpness", ratio >= q.sharpness_min_ratio, f"nitidez {ratio:.0%} da referência (mínimo {q.sharpness_min_ratio:.0%}): foco?" if ratio < q.sharpness_min_ratio else f"nitidez {ratio:.0%} da referência"))

    sim = metrics.similarity(frame.image, ref_image)
    checks.append(Check("similarity", sim >= q.similarity_min, f"imagem diferente da referência ({sim:.0%}, mínimo {q.similarity_min:.0%}): câmera movida ou cena diferente?" if sim < q.similarity_min else f"semelhança {sim:.0%}"))

    if locate is not None and meta is not None and meta.anchor is not None:
        found = locate(frame.image)
        if found is None:
            checks.append(Check("anchor", False, "objeto de referência não encontrado na imagem"))
        else:
            shift = max(abs(found[0] - meta.anchor[0]), abs(found[1] - meta.anchor[1]))
            checks.append(Check("anchor", shift <= q.anchor_tolerance, f"posição deslocada {shift:.1%} da imagem (máximo {q.anchor_tolerance:.1%})" if shift > q.anchor_tolerance else "posição conferida"))
    return checks, warnings


def check_decision_logic(bundle: JobBundle, inspect: Inspector, require_reference_set: bool = False) -> tuple[list[Check], list[str]]:
    """Step 5: run the job on the stored reference images and compare with the expected results."""
    if EXPECTED_FILE not in bundle.extra:
        if require_reference_set:
            return [Check("reference_set", False, "job sem conjunto de referência (tests/expected.yaml)")], []
        return [], ["job sem conjunto de referência: lógica de decisão não conferida"]

    expected = parse_expected(bundle.extra[EXPECTED_FILE])
    checks: list[Check] = []
    for case in expected.cases:
        name = f"case:{case.image}"
        data = bundle.extra.get(case.image)
        image = decode_image(data) if data else None
        if image is None:
            checks.append(Check(name, False, f"{case.image}: imagem ausente ou ilegível"))
            continue
        try:
            result = inspect(bundle, Frame(image=image, timestamp=0.0))
        except Exception as exc:  # a tool that crashes on a stored image is a failed case, not a crash of the verifier
            checks.append(Check(name, False, f"{case.image}: erro ao inspecionar ({type(exc).__name__}: {exc})"))
            continue
        problems = _compare(case, result, expected.tolerance)
        checks.append(Check(name, not problems, f"{case.image}: " + ("; ".join(problems) if problems else f"{result.outcome} como esperado")))
    return checks, []


def _compare(case, result: InspectionResult, tolerance: float) -> list[str]:
    problems: list[str] = []
    if result.outcome != Outcome(case.outcome):
        problems.append(f"resultado {result.outcome}, esperado {case.outcome}")
    for tool_id, want in case.scores.items():
        got = result.scores.get(tool_id)
        if got is None:
            problems.append(f"nota de '{tool_id}' ausente")
        elif abs(got - want) > tolerance:
            problems.append(f"nota de '{tool_id}' {got:.3f}, esperada {want:.3f} ± {tolerance:g}")
    if case.reason_contains and case.reason_contains not in result.reason:
        problems.append(f"motivo '{result.reason}' não contém '{case.reason_contains}'")
    return problems


def verify_job(
    bundle: JobBundle,
    *,
    inspect: Inspector,
    apply_report: ApplyReport | None = None,
    frame: Frame | None = None,
    parts: Literal["both", "camera", "decision"] = "both",
    locate: Locator | None = None,
    require_reference_set: bool = False,
) -> VerificationReport:
    camera: list[Check] = []
    decision: list[Check] = []
    warnings: list[str] = []
    if parts in ("both", "camera"):
        camera, w = check_camera_and_view(bundle, apply_report, frame, locate)
        warnings += w
    if parts in ("both", "decision"):
        decision, w = check_decision_logic(bundle, inspect, require_reference_set)
        warnings += w
    return VerificationReport(tuple(camera), tuple(decision), tuple(warnings))
