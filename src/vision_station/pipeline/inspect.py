"""The inspection pipeline: frame in, PASS / FAIL / ERROR out (architecture §7.1, FR-INS-*).

    brightness -> locator -> sharpness -> regions -> every tool -> decision (all_pass)

It never raises and never answers PASS on doubt: a dark or blurred picture, an object not found, a region
outside the picture, a tool that breaks or a job the software cannot run are all ERROR (FR-INS-6).
"""

import logging
import time
from collections.abc import Mapping
from typing import Any

import numpy as np

from vision_station.cameras import Frame
from vision_station.core.jobfiles import JobFileError, JobFiles
from vision_station.core.results import InspectionResult, Outcome
from vision_station.geometry.regions import RegionError, resolve_roi
from vision_station.jobs import Job
from vision_station.locators import Anchor, LocatorError, run_locator
from vision_station.pipeline.quality import OUT_OF_FOCUS, brightness_gate, sharp_enough
from vision_station.pipeline.stop import Stop
from vision_station.store.bundle import JobBundle
from vision_station.tools import ToolError, run_tool

log = logging.getLogger(__name__)


def _error(reason: str, started: float, timings: dict[str, Any]) -> InspectionResult:
    total = time.perf_counter() - started
    return InspectionResult(Outcome.ERROR, reason, details={"timings": {**timings, "total": total}}, duration_s=total)


NOT_FOUND = "Objeto não encontrado na posição esperada"


def _locate(job: Job, image: np.ndarray, files: JobFiles) -> Anchor | None:
    locator = job.geometry.locator
    if locator is None:
        return None
    try:
        anchor = run_locator(locator.type, locator.version, image, locator.params, files)
    except (LocatorError, JobFileError) as exc:
        raise Stop(f"Localizador não pode rodar: {exc}") from exc
    if anchor is None:
        raise Stop(NOT_FOUND)
    return anchor


def inspect_job(bundle: JobBundle, frame: Frame) -> InspectionResult:
    started = time.perf_counter()
    timings: dict[str, Any] = {}
    try:
        return _inspect(bundle, frame.image, started, timings)
    except Stop as stop:
        return _error(str(stop), started, timings)
    except Exception:  # any doubt is ERROR, whatever the cause (FR-INS-6)
        log.exception("inspection failed")
        return _error("Falha interna na inspeção, chamar a manutenção", started, timings)


def _inspect(bundle: JobBundle, image: Any, started: float, timings: dict[str, Any]) -> InspectionResult:
    job = bundle.job
    files = JobFiles(bundle.extra)
    if not isinstance(image, np.ndarray) or image.ndim not in (2, 3) or image.size == 0:
        raise Stop("Imagem inválida da câmera")

    # Brightness first; then the locator, before sharpness: an empty station is also "not sharp", and
    # "object not found" is the better reason for it. When both fail they cannot be told apart.
    t = time.perf_counter()
    brightness_gate(bundle, image)
    timings["quality"] = time.perf_counter() - t

    t = time.perf_counter()
    try:
        anchor = _locate(job, image, files)
    except Stop as stop:
        if str(stop) == NOT_FOUND and not sharp_enough(bundle, image):
            raise Stop("Objeto não encontrado ou imagem fora de foco, verificar a estação e a câmera") from None
        raise
    timings["locate"] = time.perf_counter() - t

    t = time.perf_counter()
    if not sharp_enough(bundle, image):
        raise Stop(OUT_OF_FOCUS)
    timings["quality"] += time.perf_counter() - t

    t_tools = time.perf_counter()
    scores: dict[str, float] = {}
    failures: list[str] = []
    regions: list[dict[str, Any]] = []
    tool_details: dict[str, Any] = {}
    per_tool: dict[str, float] = {}
    for tool in job.tools:
        try:
            rect, px = resolve_roi(job, tool.roi, anchor, image.shape)
        except RegionError as exc:
            raise Stop(str(exc)) from None
        x0, y0, x1, y1 = px
        t = time.perf_counter()
        try:
            result = run_tool(tool.type, tool.version, image[y0:y1, x0:x1], tool.params, files)
        except (ToolError, JobFileError) as exc:
            raise Stop(f"Ferramenta '{tool.id}' não pode rodar: {exc}") from exc
        except Exception as exc:
            log.exception("tool %s failed", tool.id)
            raise Stop(f"Ferramenta '{tool.id}' falhou: {type(exc).__name__}") from exc
        per_tool[tool.id] = time.perf_counter() - t
        score = float(result.score)
        if not 0.0 <= score <= 1.0 or score != score:
            raise Stop(f"Ferramenta '{tool.id}' devolveu pontuação inválida")
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
