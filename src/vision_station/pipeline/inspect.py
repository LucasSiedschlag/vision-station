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
from vision_station.core.errors import CATALOG, ErrorCode
from vision_station.core.jobfiles import JobFileError, JobFiles
from vision_station.core.results import FixturePose, InspectionResult, Outcome, ReasonCode, ToolReport
from vision_station.geometry.regions import PixelRect, RegionError, resolve_roi
from vision_station.jobs import Job
from vision_station.jobs.job import Tool
from vision_station.locators import Anchor, LocatorError, run_locator
from vision_station.pipeline.quality import brightness_gate, sharp_enough
from vision_station.pipeline.stop import Stop
from vision_station.store.bundle import JobBundle
from vision_station.tools import ToolError, run_tool
from vision_station.tools.base import ToolResult

log = logging.getLogger(__name__)


def _error(code: ErrorCode, reason: str, started: float, timings: dict[str, Any]) -> InspectionResult:
    total = time.perf_counter() - started
    return InspectionResult(Outcome.ERROR, reason, details={"timings": {**timings, "total": total}}, duration_s=total, error_code=int(code))




def _locate(job: Job, image: np.ndarray, files: JobFiles) -> Anchor | None:
    locator = job.geometry.locator
    if locator is None:
        return None
    try:
        anchor = run_locator(locator.type, locator.version, image, locator.params, files)
    except (LocatorError, JobFileError) as exc:
        raise Stop(ErrorCode.LOCATOR_CANNOT_RUN, f"Localizador não pode rodar: {exc}") from exc
    if anchor is None:
        raise Stop(ErrorCode.NOT_FOUND)
    return anchor


def inspect_job(bundle: JobBundle, frame: Frame) -> InspectionResult:
    started = time.perf_counter()
    timings: dict[str, Any] = {}
    try:
        return _inspect(bundle, frame.image, started, timings)
    except Stop as stop:
        return _error(stop.code, str(stop), started, timings)
    except Exception:  # any doubt is ERROR, whatever the cause (FR-INS-6)
        log.exception("inspection failed")
        return _error(ErrorCode.INTERNAL, CATALOG[ErrorCode.INTERNAL].text, started, timings)


def _inspect(bundle: JobBundle, image: Any, started: float, timings: dict[str, Any]) -> InspectionResult:
    job = bundle.job
    files = JobFiles(bundle.extra)
    if not isinstance(image, np.ndarray) or image.ndim not in (2, 3) or image.size == 0:
        raise Stop(ErrorCode.INVALID_IMAGE)

    # Brightness first; then the locator, before sharpness: an empty station is also "not sharp", and
    # "object not found" is the better reason for it. When both fail they cannot be told apart.
    t = time.perf_counter()
    brightness_gate(bundle, image)
    timings["quality"] = time.perf_counter() - t

    t = time.perf_counter()
    try:
        anchor = _locate(job, image, files)
    except Stop as stop:
        if stop.code is ErrorCode.NOT_FOUND and not sharp_enough(bundle, image):
            raise Stop(ErrorCode.NOT_FOUND_OR_BLURRED) from None
        raise
    timings["locate"] = time.perf_counter() - t

    t = time.perf_counter()
    if not sharp_enough(bundle, image):
        raise Stop(ErrorCode.OUT_OF_FOCUS)
    timings["quality"] += time.perf_counter() - t

    t_tools = time.perf_counter()
    scores: dict[str, float] = {}
    failures: list[str] = []
    regions: list[dict[str, Any]] = []
    tool_details: dict[str, Any] = {}
    per_tool: dict[str, float] = {}
    reports: list[ToolReport] = []
    reason_codes: list[ReasonCode] = []
    for tool in job.tools:
        try:
            px, result, score, elapsed = _run(tool, job, anchor, image, files)
        except Stop as stop:
            if tool.affects_result:
                raise
            # an informative tool never decides, not even by failing to run: noted on its own entry (FR-INS-13)
            reports.append(ToolReport(tool.id, tool.type, tool.version, False, 0.0, affects_result=False, error=str(stop), error_code=int(stop.code)))
            continue
        per_tool[tool.id] = elapsed
        scores[tool.id] = score
        tool_details[tool.id] = dict(result.details)
        regions.append({"tool": tool.id, "roi": tool.roi, "rect": list(px), "passed": bool(result.passed), "affects_result": tool.affects_result})
        report = _report(tool, result, score)
        reports.append(report)
        if not result.passed and tool.affects_result:
            failures.append(result.reason(tool.reason_fail))
            reason_codes.extend(ReasonCode(tool.id, f"{tool.type}.{c.code}") for c in report.criteria if not c.passed)
    timings["tools"] = time.perf_counter() - t_tools
    timings["per_tool"] = per_tool

    total = time.perf_counter() - started
    timings["total"] = total
    fixtures = () if anchor is None else (_pose(anchor),)
    details: Mapping[str, Any] = {
        "timings": timings,
        "anchor": None if anchor is None else {"rect": list(anchor.rect), "score": anchor.score},
        "regions": regions,
        "tools": tool_details,
    }
    if failures:
        return InspectionResult(
            Outcome.FAIL, "; ".join(failures), scores=scores, details=details, duration_s=total,
            reason_codes=tuple(reason_codes), tools=tuple(reports), fixtures=fixtures,
        )
    return InspectionResult(Outcome.PASS, scores=scores, details=details, duration_s=total, tools=tuple(reports), fixtures=fixtures)


def _pose(anchor: Anchor) -> FixturePose:
    x0, y0, x1, y1 = anchor.rect
    return FixturePose("anchor", (x0 + x1) / 2, (y0 + y1) / 2, angle=None, scale=None, score=float(anchor.score))


def _run(tool: Tool, job: Job, anchor: Anchor | None, image: np.ndarray, files: JobFiles) -> tuple[PixelRect, ToolResult, float, float]:
    """One tool on its region: the region, the result, the checked score and the time it took. Raises Stop."""
    try:
        _, px = resolve_roi(job, tool.roi, anchor, image.shape)
    except RegionError as exc:
        raise Stop(ErrorCode.REGION_OUTSIDE, str(exc)) from None
    x0, y0, x1, y1 = px
    t = time.perf_counter()
    try:
        result = run_tool(tool.type, tool.version, image[y0:y1, x0:x1], tool.params, files)
    except (ToolError, JobFileError) as exc:
        raise Stop(ErrorCode.TOOL_CANNOT_RUN, f"Ferramenta '{tool.id}' não pode rodar: {exc}") from exc
    except Exception as exc:
        log.exception("tool %s failed", tool.id)
        raise Stop(ErrorCode.TOOL_FAILED, f"Ferramenta '{tool.id}' falhou: {type(exc).__name__}") from exc
    elapsed = time.perf_counter() - t
    score = float(result.score)
    if not 0.0 <= score <= 1.0 or score != score:
        raise Stop(ErrorCode.INVALID_SCORE, f"Ferramenta '{tool.id}' devolveu pontuação inválida")
    return px, result, score, elapsed


def _report(tool: Tool, result: ToolResult, score: float) -> ToolReport:
    """The tool's part of the result contract: its numeric measures with units, and its criteria (TD-22)."""
    values = {
        name: float(result.values[name])
        for name in result.units
        if isinstance(result.values.get(name), int | float) and not isinstance(result.values.get(name), bool)
    }
    units = {name: unit for name, unit in result.units.items() if name in values}
    return ToolReport(tool.id, tool.type, tool.version, bool(result.passed), score, values, units, tuple(result.criteria), tool.affects_result)
