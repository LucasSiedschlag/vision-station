"""The inspection pipeline: frame in, PASS / FAIL / ERROR out (architecture §7.1, FR-INS-*).

    brightness -> locator -> sharpness -> regions -> every tool -> decision (all_pass)

It never raises and never answers PASS on doubt: a dark or blurred picture, an object not found, a region
outside the picture, a tool that breaks or a job the software cannot run are all ERROR (FR-INS-6).
"""

import logging
import time
from dataclasses import replace
from collections.abc import Mapping
from typing import Any

import numpy as np

from vision_station.cameras import Frame
from vision_station.core.errors import CATALOG, ErrorCode
from vision_station.core.i18n import join, tr
from vision_station.core.jobfiles import JobFileError, JobFiles
from vision_station.core.results import FixturePose, InspectionResult, Outcome, ReasonCode, ToolReport
from vision_station.geometry.regions import RegionError, cut_region
from vision_station.geometry.pose import PixelRect
from vision_station.jobs import Job
from vision_station.jobs.job import FixtureSpec, Tool
from vision_station.geometry.pose import Cut, Fixture, RegionOutside, compose, cut
from vision_station.locators import LocatorError, run_locator
from vision_station.pipeline.marks import to_frame_marks
from vision_station.pipeline.quality import brightness_gate, sharp_enough
from vision_station.pipeline.stop import Stop
from vision_station.store.bundle import JobBundle
from vision_station.tools import ToolError, run_tool
from vision_station.tools.base import ToolResult

log = logging.getLogger(__name__)


def _error(code: ErrorCode, reason: str, started: float, timings: dict[str, Any]) -> InspectionResult:
    total = time.perf_counter() - started
    return InspectionResult(Outcome.ERROR, reason, details={"timings": {**timings, "total": total}}, duration_s=total, error_code=int(code))




def _within(spec: FixtureSpec, fixture: Fixture) -> None:
    """The pose must be inside what the job allows: an object that is turned too far, too large, too small or somewhere else
    is not something the job can judge, so it is ERROR, never FAIL (FR-INS-11)."""
    allowed = spec.range
    cx, cy = fixture.centre
    lo, hi = allowed.angle
    if not lo <= fixture.angle <= hi:
        raise Stop(ErrorCode.OUT_OF_POSITION, tr("Objeto '{name}' girado {angle:.1f}° (permitido {lo:g}° a {hi:g}°)", name=spec.name, angle=fixture.angle, lo=lo, hi=hi))
    lo, hi = allowed.scale
    if not lo <= fixture.scale <= hi:
        raise Stop(ErrorCode.OUT_OF_POSITION, tr("Objeto '{name}' com tamanho {scale:.2f}× o ensinado (permitido {lo:g}× a {hi:g}×)", name=spec.name, scale=fixture.scale, lo=lo, hi=hi))
    if allowed.position is not None:
        x0, y0, x1, y1 = allowed.position
        if not (x0 <= cx <= x1 and y0 <= cy <= y1):
            raise Stop(ErrorCode.OUT_OF_POSITION, tr("Objeto '{name}' fora da área permitida", name=spec.name))


def _locate(job: Job, image: np.ndarray, files: JobFiles, found: dict[str, Fixture] | None = None) -> dict[str, Fixture]:
    """The fixtures of the job, in order; one that is searched inside another looks in that one's upright cut (FR-INS-12).
    `found` is filled as they are found, so a caller that gets a `Stop` still has the ones before it."""
    found = {} if found is None else found
    for spec in job.geometry.fixtures:
        parent = found.get(spec.inside) if spec.inside else None
        searched, inner = image, None
        if parent is not None:
            try:
                inner = cut(image, (0.0, 0.0, 1.0, 1.0), parent)
            except RegionOutside:
                raise Stop(ErrorCode.REGION_OUTSIDE, tr("Região '{name}' fora da imagem", name=spec.inside)) from None
            searched = inner.image
        try:
            fixture = run_locator(spec.locator.type, spec.locator.version, searched, spec.locator.params, files)
        except (LocatorError, JobFileError) as exc:
            raise Stop(ErrorCode.LOCATOR_CANNOT_RUN, tr("Localizador não pode rodar: {exc}", exc=exc)) from exc
        if fixture is None:
            raise Stop(ErrorCode.NOT_FOUND)
        if inner is not None:
            fixture = compose(inner, parent, fixture, image.shape)
        fixture = replace(fixture, name=spec.name)
        found[spec.name] = fixture  # kept even when it is refused: the editor shows how far off it is
        _within(spec, fixture)
    return found


def locate_fixtures(bundle: JobBundle, image: np.ndarray) -> tuple[dict[str, Fixture], Stop | None]:
    """Only the locating step of the pipeline: the fixtures found, and why it stopped when it did not find them all or one is
    out of its range. The editor's anchor step shows it on every sample (docs/frontend.md §7.3)."""
    found: dict[str, Fixture] = {}
    try:
        _locate(bundle.job, image, JobFiles(bundle.extra), found)
    except Stop as stop:
        return found, stop
    return found, None


def inspect_job(bundle: JobBundle, frame: Frame) -> InspectionResult:
    started = time.perf_counter()
    timings: dict[str, Any] = {}
    try:
        return _inspect(bundle, frame.image, started, timings)
    except Stop as stop:
        return _error(stop.code, stop.text, started, timings)
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
        fixtures = _locate(job, image, files)
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
            region, result, score, elapsed = _run(tool, job, fixtures, image, files)
        except Stop as stop:
            if tool.affects_result:
                raise
            # an informative tool never decides, not even by failing to run: noted on its own entry (FR-INS-13)
            reports.append(ToolReport(tool.id, tool.type, tool.version, False, 0.0, affects_result=False, error=stop.text, error_code=int(stop.code)))
            continue
        per_tool[tool.id] = elapsed
        scores[tool.id] = score
        tool_details[tool.id] = dict(result.details)
        entry = {"tool": tool.id, "roi": tool.roi, "rect": list(region.px), "passed": bool(result.passed), "affects_result": tool.affects_result}
        if not np.array_equal(region.to_frame[:, :2], np.eye(2)):  # turned: the outline, for the overlay
            entry["corners"] = [[round(x, 1), round(y, 1)] for x, y in region.corners]
        regions.append(entry)
        report = _report(tool, result, score, region, image.shape)
        reports.append(report)
        if not result.passed and tool.affects_result:
            failures.append(tool.reason_fail.filled(result.values))
            reason_codes.extend(ReasonCode(tool.id, f"{tool.type}.{c.code}") for c in report.criteria if not c.passed)
    timings["tools"] = time.perf_counter() - t_tools
    timings["per_tool"] = per_tool

    total = time.perf_counter() - started
    timings["total"] = total
    poses = tuple(_pose(f) for f in fixtures.values())
    first = next(iter(fixtures.values()), None)
    details: Mapping[str, Any] = {
        "timings": timings,
        "anchor": None if first is None else outline(first, image.shape),
        "fixtures": [outline(f, image.shape) | {"name": f.name} for f in fixtures.values()],
        "regions": regions,
        "tools": tool_details,
    }
    if failures:
        return InspectionResult(
            Outcome.FAIL, join(failures), scores=scores, details=details, duration_s=total,
            reason_codes=tuple(reason_codes), tools=tuple(reports), fixtures=poses,
        )
    return InspectionResult(Outcome.PASS, scores=scores, details=details, duration_s=total, tools=tuple(reports), fixtures=poses)


def _pose(fixture: Fixture) -> FixturePose:
    x, y = fixture.centre
    return FixturePose(fixture.name, x, y, angle=fixture.angle, scale=fixture.scale, score=float(fixture.score))


def outline(fixture: Fixture, shape: tuple[int, ...]) -> dict[str, Any]:
    """What the API and the overlay get of a fixture: its upright box (the one the locator gave, when it is not turned), the pose, and the outline."""
    out: dict[str, Any] = {"rect": list(fixture.bounds(shape)), "taught": list(fixture.rect), "score": fixture.score, "angle": fixture.angle, "scale": fixture.scale}
    if not fixture.upright:
        out["corners"] = [[round(float(x), 1), round(float(y), 1)] for x, y in fixture.corners(shape)]
    return out


def _run(tool: Tool, job: Job, fixtures: dict[str, Fixture], image: np.ndarray, files: JobFiles) -> tuple[Cut, ToolResult, float, float]:
    """One tool on its region: the region, the result, the checked score and the time it took. Raises Stop."""
    try:
        region = cut_region(job, tool.roi, fixtures, image)
    except RegionError as exc:
        raise Stop(ErrorCode.REGION_OUTSIDE, exc.text) from None
    t = time.perf_counter()
    try:
        result = run_tool(tool.type, tool.version, region.image, tool.params, files)
    except (ToolError, JobFileError) as exc:
        raise Stop(ErrorCode.TOOL_CANNOT_RUN, tr("Ferramenta '{tool}' não pode rodar: {exc}", tool=tool.id, exc=exc)) from exc
    except Exception as exc:
        log.exception("tool %s failed", tool.id)
        raise Stop(ErrorCode.TOOL_FAILED, tr("Ferramenta '{tool}' falhou: {kind}", tool=tool.id, kind=type(exc).__name__)) from exc
    elapsed = time.perf_counter() - t
    score = float(result.score)
    if not 0.0 <= score <= 1.0 or score != score:
        raise Stop(ErrorCode.INVALID_SCORE, tr("Ferramenta '{tool}' devolveu pontuação inválida", tool=tool.id))
    return region, result, score, elapsed


def _fractions(px: PixelRect, shape: tuple[int, ...]) -> tuple[float, float, float, float]:
    """A pixel rectangle as fractions of the frame, so a client can draw it on a picture of any size."""
    height, width = shape[:2]
    x0, y0, x1, y1 = px
    return (x0 / width, y0 / height, x1 / width, y1 / height)


def _report(tool: Tool, result: ToolResult, score: float, region: Cut, shape: tuple[int, ...]) -> ToolReport:
    """The tool's part of the result contract: its numeric measures with units, its criteria (TD-22), and its marks mapped to the frame."""
    values = {
        name: float(result.values[name])
        for name in result.units
        if isinstance(result.values.get(name), int | float) and not isinstance(result.values.get(name), bool)
    }
    units = {name: unit for name, unit in result.units.items() if name in values}
    return ToolReport(tool.id, tool.type, tool.version, bool(result.passed), score, values, units, tuple(result.criteria), tool.affects_result, region=_fractions(region.px, shape), marks=to_frame_marks(result.marks, region, shape))
