"""The inspection pipeline: frame in, PASS / FAIL / ERROR out (architecture §7.1, FR-INS-*).

    quality gate -> locator -> regions -> every tool -> decision (all_pass)

It never raises and never answers PASS on doubt: a dark or blurred picture, an object not found, a region
outside the picture, a tool that breaks or a job the software cannot run are all ERROR (FR-INS-6).
"""

import logging
import time
from collections.abc import Mapping
from typing import Any

import cv2
import numpy as np

from vision_station.cameras import Frame
from vision_station.jobs import Job
from vision_station.locators import Anchor, LocatorError, run_locator
from vision_station.results import InspectionResult, Outcome
from vision_station.store.bundle import JobBundle
from vision_station.tools import ToolError, run_tool
from vision_station.verification import metrics
from vision_station.verification.reference import REFERENCE_META, parse_meta

log = logging.getLogger(__name__)

PixelRect = tuple[int, int, int, int]  # x0, y0, x1, y1


class _Stop(Exception):
    """The inspection cannot go on; carries the ERROR text for the operator."""


def _error(reason: str, started: float, timings: dict[str, Any]) -> InspectionResult:
    total = time.perf_counter() - started
    return InspectionResult(Outcome.ERROR, reason, details={"timings": {**timings, "total": total}}, duration_s=total)


def _quality_gate(bundle: JobBundle, image: np.ndarray) -> None:
    quality = bundle.job.quality
    level = metrics.brightness(image)
    if level < quality.brightness.min:
        raise _Stop("Imagem escura demais, verificar a iluminação")
    if level > quality.brightness.max:
        raise _Stop("Imagem clara demais, verificar a iluminação")
    raw = bundle.extra.get(REFERENCE_META)
    if raw is None:
        return  # a job without a reference has nothing to compare sharpness with; verification asks for it
    reference = parse_meta(raw).sharpness
    if reference > 0 and metrics.sharpness(image) < quality.sharpness_min_ratio * reference:
        raise _Stop("Imagem fora de foco, verificar a lente e a câmera")


def _locate(job: Job, image: np.ndarray) -> Anchor | None:
    locator = job.geometry.locator
    if locator is None:
        return None
    try:
        anchor = run_locator(locator.type, locator.version, image, locator.params)
    except LocatorError as exc:
        raise _Stop(f"Localizador não pode rodar: {exc}") from exc
    if anchor is None:
        raise _Stop("Objeto não encontrado na posição esperada")
    return anchor


def resolve_roi(job: Job, name: str, anchor: Anchor | None, shape: tuple[int, ...]) -> tuple[tuple[float, float, float, float], PixelRect]:
    """The region `name` as fractions of the frame and as pixels. Raises _Stop if it has no pixels."""
    if name == "frame":
        rect = (0.0, 0.0, 1.0, 1.0)
    elif name == "anchor":
        if anchor is None:
            raise _Stop("Região 'anchor' sem localizador")
        rect = anchor.rect
    else:
        roi = job.geometry.rois[name]
        if roi.relative_to == "frame":
            rect = roi.rect
        else:
            if anchor is None:
                raise _Stop(f"Região '{name}' depende do objeto, que não foi localizado")
            ax0, ay0, ax1, ay1 = anchor.rect
            w, h = ax1 - ax0, ay1 - ay0
            x0, y0, x1, y1 = roi.rect
            rect = (ax0 + x0 * w, ay0 + y0 * h, ax0 + x1 * w, ay0 + y1 * h)
    height, width = shape[:2]
    px = (round(rect[0] * width), round(rect[1] * height), round(rect[2] * width), round(rect[3] * height))
    if px[2] - px[0] < 1 or px[3] - px[1] < 1 or px[0] < 0 or px[1] < 0 or px[2] > width or px[3] > height:
        raise _Stop(f"Região '{name}' fora da imagem")
    return rect, px


def inspect_job(bundle: JobBundle, frame: Frame) -> InspectionResult:
    started = time.perf_counter()
    timings: dict[str, Any] = {}
    try:
        return _inspect(bundle, frame.image, started, timings)
    except _Stop as stop:
        return _error(str(stop), started, timings)
    except Exception:  # any doubt is ERROR, whatever the cause (FR-INS-6)
        log.exception("inspection failed")
        return _error("Falha interna na inspeção, chamar a manutenção", started, timings)


def _inspect(bundle: JobBundle, image: Any, started: float, timings: dict[str, Any]) -> InspectionResult:
    job = bundle.job
    if not isinstance(image, np.ndarray) or image.ndim not in (2, 3) or image.size == 0:
        raise _Stop("Imagem inválida da câmera")

    t = time.perf_counter()
    _quality_gate(bundle, image)
    timings["quality"] = time.perf_counter() - t

    t = time.perf_counter()
    anchor = _locate(job, image)
    timings["locate"] = time.perf_counter() - t

    t_tools = time.perf_counter()
    scores: dict[str, float] = {}
    failures: list[str] = []
    regions: list[dict[str, Any]] = []
    tool_details: dict[str, Any] = {}
    per_tool: dict[str, float] = {}
    for tool in job.tools:
        rect, px = resolve_roi(job, tool.roi, anchor, image.shape)
        x0, y0, x1, y1 = px
        t = time.perf_counter()
        try:
            result = run_tool(tool.type, tool.version, image[y0:y1, x0:x1], tool.params)
        except ToolError as exc:
            raise _Stop(f"Ferramenta '{tool.id}' não pode rodar: {exc}") from exc
        except Exception as exc:
            log.exception("tool %s failed", tool.id)
            raise _Stop(f"Ferramenta '{tool.id}' falhou: {type(exc).__name__}") from exc
        per_tool[tool.id] = time.perf_counter() - t
        score = float(result.score)
        if not 0.0 <= score <= 1.0 or score != score:
            raise _Stop(f"Ferramenta '{tool.id}' devolveu pontuação inválida")
        scores[tool.id] = score
        tool_details[tool.id] = dict(result.details)
        regions.append({"tool": tool.id, "roi": tool.roi, "rect": list(px), "passed": bool(result.passed)})
        if not result.passed:
            failures.append(result.reason(tool.reason_fail))
    timings["tools"] = time.perf_counter() - t_tools
    timings["per_tool"] = per_tool

    total = time.perf_counter() - started
    timings["total"] = total
    details: Mapping[str, Any] = {
        "timings": timings,
        "anchor": None if anchor is None else {"rect": list(anchor.rect), "score": anchor.score},
        "regions": regions,
        "tools": tool_details,
    }
    if failures:
        return InspectionResult(Outcome.FAIL, "; ".join(failures), scores=scores, details=details, duration_s=total)
    return InspectionResult(Outcome.PASS, scores=scores, details=details, duration_s=total)


_GREEN, _RED, _YELLOW = (60, 190, 60), (50, 50, 230), (0, 200, 240)


def draw_overlay(image: np.ndarray, result: InspectionResult) -> np.ndarray:
    """A copy of the frame with the anchor and every tool's region drawn: green passed, red failed."""
    out = image.copy() if image.ndim == 3 else cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    h, w = out.shape[:2]
    thick = max(2, round(max(h, w) / 400))
    anchor = result.details.get("anchor")
    if anchor:
        x0, y0, x1, y1 = anchor["rect"]
        cv2.rectangle(out, (round(x0 * w), round(y0 * h)), (round(x1 * w), round(y1 * h)), _YELLOW, thick)
    for region in result.details.get("regions", []):
        x0, y0, x1, y1 = region["rect"]
        color = _GREEN if region["passed"] else _RED
        cv2.rectangle(out, (x0, y0), (x1 - 1, y1 - 1), color, thick)
        cv2.putText(out, region["tool"], (x0 + 4, y0 + 8 + 10 * thick), cv2.FONT_HERSHEY_SIMPLEX, 0.3 * thick, color, thick)
    return out
