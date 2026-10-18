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
from vision_station.core.i18n import join, tr
from vision_station.core.results import InspectionResult, Outcome
from vision_station.store import JobBundle
from vision_station.algorithms import metrics
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
    message: str  # a Msg (Portuguese, translated at the API), for the screen


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
            return tr("Job verificado")
        return join(c.message for c in self.failures())


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
        checks.append(Check("settings", False, tr("ajustes da câmera não aplicados")))
    else:
        rejected = sorted(k for k, s in apply_report.status.items() if s is SettingStatus.REJECTED)
        if rejected:
            detail = join(tr("{setting}: {detail}", setting=k, detail=apply_report.detail.get(k) or tr("recusado")) for k in rejected)
            checks.append(Check("settings", False, tr("ajuste não aplicado ({detail})", detail=detail)))
        else:
            checks.append(Check("settings", True, tr("ajustes da câmera aplicados")))
        warnings += [tr("{setting}: {detail}", setting=k, detail=apply_report.detail.get(k) or tr("não suportado")) for k, s in sorted(apply_report.status.items()) if s is SettingStatus.NOT_SUPPORTED]

    if frame is None:
        checks.append(Check("frame", False, tr("sem imagem da câmera")))
        return checks, warnings
    checks.append(Check("frame", True, tr("imagem recebida")))

    q = bundle.job.quality
    bright = metrics.brightness(frame.image)
    in_range = q.brightness.min <= bright <= q.brightness.max
    checks.append(Check("brightness", in_range, tr("brilho {value:.0f} (esperado {low:g} a {high:g})", value=bright, low=q.brightness.min, high=q.brightness.max) if not in_range else tr("brilho {value:.0f}", value=bright)))

    ref_png = bundle.extra.get(REFERENCE_IMAGE)
    ref_image = decode_image(ref_png) if ref_png else None
    if ref_image is None:
        warnings.append(tr("job sem imagem de referência: nitidez, semelhança e posição não conferidas"))
        return checks, warnings

    meta = parse_meta(bundle.extra[REFERENCE_META]) if REFERENCE_META in bundle.extra else None
    ref_sharp = meta.sharpness if meta else metrics.sharpness(ref_image)
    sharp = metrics.sharpness(frame.image)
    ratio = sharp / ref_sharp if ref_sharp > 0 else 1.0
    checks.append(Check("sharpness", ratio >= q.sharpness_min_ratio, tr("nitidez {ratio:.0%} da referência (mínimo {minimum:.0%}): foco?", ratio=ratio, minimum=q.sharpness_min_ratio) if ratio < q.sharpness_min_ratio else tr("nitidez {ratio:.0%} da referência", ratio=ratio)))

    sim = metrics.similarity(frame.image, ref_image)
    checks.append(Check("similarity", sim >= q.similarity_min, tr("imagem diferente da referência ({value:.0%}, mínimo {minimum:.0%}): câmera movida ou cena diferente?", value=sim, minimum=q.similarity_min) if sim < q.similarity_min else tr("semelhança {value:.0%}", value=sim)))

    if locate is not None and meta is not None and meta.anchor is not None:
        found = locate(frame.image)
        if found is None:
            checks.append(Check("anchor", False, tr("objeto de referência não encontrado na imagem")))
        else:
            shift = max(abs(found[0] - meta.anchor[0]), abs(found[1] - meta.anchor[1]))
            checks.append(Check("anchor", shift <= q.anchor_tolerance, tr("posição deslocada {shift:.1%} da imagem (máximo {maximum:.1%})", shift=shift, maximum=q.anchor_tolerance) if shift > q.anchor_tolerance else tr("posição conferida")))
    return checks, warnings


@dataclass(frozen=True)
class CaseRun:
    """One image of the reference set run through the job (what Validar shows and activation checks)."""

    image: str
    expected: str  # PASS, FAIL or ERROR
    outcome: str | None  # what the job said; None: it could not be run
    ok: bool
    message: str  # a Msg: "<image>: <what>"
    reason: str = ""  # a Msg
    duration_ms: int | None = None


def run_reference_set(bundle: JobBundle, inspect: Inspector) -> list[CaseRun]:
    """Run the job on every image of its reference set (tests/expected.yaml) and compare with what is expected."""
    if EXPECTED_FILE not in bundle.extra:
        return []
    expected = parse_expected(bundle.extra[EXPECTED_FILE])
    informative = {t.id for t in bundle.job.tools if not t.affects_result}
    runs: list[CaseRun] = []
    for case in expected.cases:
        data = bundle.extra.get(case.image)
        image = decode_image(data) if data else None
        if image is None:
            runs.append(CaseRun(case.image, case.outcome, None, False, tr("{image}: imagem ausente ou ilegível", image=case.image)))
            continue
        try:
            result = inspect(bundle, Frame(image=image, timestamp=0.0))
        except Exception as exc:  # a tool that crashes on a stored image is a failed case, not a crash of the verifier
            runs.append(CaseRun(case.image, case.outcome, None, False, tr("{image}: erro ao inspecionar ({kind}: {exc})", image=case.image, kind=type(exc).__name__, exc=exc)))
            continue
        problems = _compare(case, result, expected.tolerance, informative)
        message = tr("{image}: {what}", image=case.image, what=join(problems) if problems else tr("{outcome} como esperado", outcome=result.outcome))
        runs.append(CaseRun(case.image, case.outcome, str(result.outcome), not problems, message, result.reason, round(result.duration_s * 1000)))
    return runs


def check_decision_logic(bundle: JobBundle, inspect: Inspector, require_reference_set: bool = False) -> tuple[list[Check], list[str]]:
    """Step 5: run the job on the stored reference images and compare with the expected results."""
    if EXPECTED_FILE not in bundle.extra:
        if require_reference_set:
            return [Check("reference_set", False, tr("job sem conjunto de referência (tests/expected.yaml)"))], []
        return [], [tr("job sem conjunto de referência: lógica de decisão não conferida")]
    return [Check(f"case:{run.image}", run.ok, run.message) for run in run_reference_set(bundle, inspect)], []


def _compare(case, result: InspectionResult, tolerance: float, informative: frozenset[str] | set[str] = frozenset()) -> list[str]:
    problems: list[str] = []  # Msgs
    if result.outcome != Outcome(case.outcome):
        problems.append(tr("resultado {got}, esperado {want}", got=result.outcome, want=case.outcome))
    for tool_id, want in case.scores.items():
        got = result.scores.get(tool_id)
        if got is None:
            if tool_id not in informative:  # an informative tool that could not run decides nothing (FR-INS-13)
                problems.append(tr("nota de '{tool}' ausente", tool=tool_id))
        elif abs(got - want) > tolerance:
            problems.append(tr("nota de '{tool}' {got:.3f}, esperada {want:.3f} ± {tolerance:g}", tool=tool_id, got=got, want=want, tolerance=tolerance))
    if case.reason_contains and case.reason_contains not in result.reason:
        problems.append(tr("motivo '{reason}' não contém '{expected}'", reason=result.reason, expected=case.reason_contains))
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
