"""The built-in benchmark: times every tool and locator on a fixed workload, classifies the PC as tier M or R and
proposes thread limits (FR-ADM-5, TD-28, NFR-PERF-5; V8 of architecture §15.3).

    <data root>/system/benchmark.json        the last report

The workload is synthetic and the same on every PC, so two reports compare. The thresholds, budgets and thread
caps are project values (document 02 §7): they are `BenchmarkSettings`, the `benchmark` section of system.yaml, and stay
*proposed* until bench test B-1 on one real unit of each tier. A tool that needs a file of the job (a `detect`
model) cannot be timed here and is listed with the reason. Nothing is applied to the program: the thread limits
are proposals in the report.
"""

import json
import math
import os
import platform
import statistics
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import zxingcpp

from vision_station.locators import locator_types, run_locator
from vision_station.core.i18n import Msg, render, tr
from vision_station.jobs.job import PresenceTrigger
from vision_station.station.trigger import PresenceDetector
from vision_station.system.config import SYSTEM_DIR, BenchmarkSettings, Tier
from vision_station.tools import run_tool, tool_types

REPORT_FILE = "benchmark.json"


@dataclass(frozen=True)
class Workload:
    image: np.ndarray
    params: dict[str, Any]
    files: dict[str, bytes] = field(default_factory=dict)


def key(kind: str, name: str, version: int) -> str:
    return f"{kind}:{name}:{version}"


def _size(megapixels: float) -> tuple[int, int]:
    """Rows and columns of a 4:3 picture of this many megapixels."""
    width = round(math.sqrt(megapixels * 1e6 * 4 / 3))
    return round(width * 3 / 4), width


def _textured(megapixels: float) -> np.ndarray:
    rows, cols = _size(megapixels)
    blocks = np.random.default_rng(5).integers(40, 220, (rows // 8 + 1, cols // 8 + 1, 3), dtype=np.uint8)
    return cv2.resize(blocks, (cols, rows), interpolation=cv2.INTER_NEAREST)


def _template_of(image: np.ndarray) -> dict[str, bytes]:
    rows, cols = image.shape[:2]
    y, x = rows // 3, cols // 3
    return {"t.png": cv2.imencode(".png", image[y : y + 64, x : x + 64])[1].tobytes()}


def _color(mp: float) -> Workload:
    image = np.full((*_size(mp), 3), 128, np.uint8)
    image[:, : image.shape[1] // 2] = (200, 90, 30)
    return Workload(image, {"hue": [100, 130], "s_min": 60, "min_fraction": 0.1, "axis": "x", "max_gap": 0.6})


def _brightness(mp: float) -> Workload:
    return Workload(_textured(mp), {"min_mean": 20, "max_mean": 230, "max_std": 100, "max_above": 0.9})


def _blob_tool(mp: float) -> Workload:
    image = np.zeros(_size(mp), np.uint8)
    rows, cols = image.shape
    for i in range(1, 6):  # five parts of a twentieth of the width
        image[rows // 4 : rows // 2, i * cols // 7 : i * cols // 7 + cols // 20] = 255
    return Workload(image, {"mode": "light", "min_count": 1, "max_count": 10, "max_largest": rows * cols})


def _edge(mp: float) -> Workload:
    image = np.full(_size(mp), 40, np.uint8)
    cols = image.shape[1]
    image[:, cols // 5 : cols // 5 * 3] = 200  # a bar across the whole picture
    return Workload(image, {"mode": "width", "min_distance": cols // 10, "max_distance": cols})


def _pattern_v2(mp: float) -> Workload:
    image = _textured(mp)
    return Workload(image, {"template": "t.png", "angles": [-20, 20], "scales": [0.9, 1.1]}, _template_of(image))


def _compare(mp: float) -> Workload:
    """A textured region and a model taught from five noisy copies of it, shifted by a pixel: the model is built here, not timed."""
    from vision_station.algorithms.variation import teach

    base = _textured(mp)
    rng = np.random.default_rng(7)
    good = []
    for i in range(5):
        shifted = np.roll(base, (i % 2, i // 2 % 2), axis=(0, 1))
        good.append(np.clip(shifted.astype(np.float32) + rng.normal(0, 2, base.shape), 0, 255).astype(np.uint8))
    return Workload(base, {"model": "models/m.var", "max_area": float(base.shape[0] * base.shape[1])}, {"models/m.var": teach(good)})


def _pattern(mp: float) -> Workload:
    image = _textured(mp)
    return Workload(image, {"template": "t.png", "min_score": 0.7}, _template_of(image))


def _code(mp: float) -> Workload:
    image = np.full((*_size(mp), 3), 255, np.uint8)
    qr = np.array(zxingcpp.create_barcode("BENCH-1", zxingcpp.BarcodeFormat.QRCode).to_image(scale=max(2, image.shape[0] // 60)))
    y, x = (image.shape[0] - qr.shape[0]) // 2, (image.shape[1] - qr.shape[1]) // 2
    image[y : y + qr.shape[0], x : x + qr.shape[1]] = qr[..., None]
    return Workload(image, {"expect": "BENCH-1"})


def _locate_template(mp: float) -> Workload:
    image = _textured(mp)
    return Workload(image, {"template": "t.png"}, _template_of(image))


def _locate_shape(mp: float) -> Workload:
    image = _textured(mp)
    return Workload(image, {"template": "t.png", "angles": [-20, 20], "scales": [0.9, 1.1]}, _template_of(image))


def _dark_part(mp: float) -> Workload:
    image = np.full((*_size(mp), 3), (205, 205, 200), np.uint8)
    rows, cols = image.shape[:2]
    image[rows // 3 : rows // 2, cols // 3 : cols // 2] = (70, 70, 75)
    return Workload(image, {"mode": "dark"})


def _corner(mp: float) -> Workload:
    """A dark part with its top-left corner at a third of the frame; a caliper window along each of its two edges."""
    image = np.full((*_size(mp), 3), (205, 205, 200), np.uint8)
    rows, cols = image.shape[:2]
    image[rows // 3 : rows // 2, cols // 3 : cols // 2] = (70, 70, 75)
    third, half = 1 / 3, 1 / 2
    vertical = {"rect": [third - 0.05, third + 0.02, third + 0.05, half - 0.02], "polarity": "falling"}
    horizontal = {"rect": [third + 0.02, third - 0.05, half - 0.02, third + 0.05], "polarity": "falling"}
    return Workload(image, {"vertical": vertical, "horizontal": horizontal, "taught_rect": [third, third, half, half], "taught_corner": [third, third]})


def _fixed(mp: float) -> Workload:
    return Workload(np.zeros((*_size(mp), 3), np.uint8), {"rect": [0.2, 0.2, 0.8, 0.8]})


WORKLOADS: dict[str, Callable[[float], Workload]] = {
    key("tool", "blob", 1): _blob_tool,
    key("tool", "brightness", 1): _brightness,
    key("tool", "color", 1): _color,
    key("tool", "compare", 1): _compare,
    key("tool", "edge", 1): _edge,
    key("tool", "pattern", 1): _pattern,
    key("tool", "pattern", 2): _pattern_v2,
    key("tool", "code", 1): _code,
    key("locator", "edges", 1): _corner,
    key("locator", "fixed", 1): _fixed,
    key("locator", "shape", 1): _locate_shape,
    key("locator", "template", 1): _locate_template,
    key("locator", "blob", 1): _dark_part,
    key("locator", "blob", 2): _dark_part,
}
# types that cannot be timed here, and why (a code in the report; the text is for the screen)
UNMEASURED: dict[str, str] = {key("tool", "detect", 1): "needs_job_model"}
REASONS: dict[str, Msg] = {"needs_job_model": tr("Precisa do modelo de um job: a latência está no cartão do modelo")}


def registered() -> list[str]:
    return [key("tool", n, v) for n, v in tool_types()] + [key("locator", n, v) for n, v in locator_types()]


def _time(kind: str, name: str, version: int, load: Workload, repeats: int, clock: Callable[[], float]) -> float:
    def once() -> None:
        if kind == "tool":
            run_tool(name, version, load.image, load.params, load.files)
        else:
            run_locator(name, version, load.image, load.params, load.files)

    once()  # the first run loads the code and warms the caches
    times = []
    for _ in range(repeats):
        start = clock()
        once()
        times.append((clock() - start) * 1000.0)
    return statistics.median(times)


def _idle_trigger(settings: BenchmarkSettings, tier: Tier | None, cpus: int, cpu_clock: Callable[[], float]) -> dict[str, Any]:
    """The image trigger while it waits for an object (NFR-PERF-7): the CPU time `PresenceDetector.update` takes per frame, on a
    picture of `idle_megapixels` with the region over the whole picture (the worst case), as a share of the whole PC at the camera
    rate. It is the trigger's own work: the camera driver's decoding needs the real camera and is not in it. CPU time (of every
    thread) is what counts, not the clock on the wall."""
    rows, cols = _size(settings.idle_megapixels)
    empty = _textured(settings.idle_megapixels)
    busy = empty.copy()
    busy[rows // 4 : rows // 2, cols // 4 : cols // 2] = 250  # an object in the area, so the motion and presence paths both run
    detector = PresenceDetector(PresenceTrigger(roi=(0, 0, 1, 1), still_ms=500, rearm="object_absent", diff_threshold=25, min_area=0.05, motion_area=0.01))
    detector.update(empty, 0.0)  # the first frame is the empty scene and warms the caches
    start = cpu_clock()
    for i in range(settings.idle_frames):
        detector.update(busy if (i // 4) % 2 else empty, (i + 1) / settings.idle_fps)
    ms = (cpu_clock() - start) * 1000.0 / settings.idle_frames
    limit = settings.idle_cpu_max_pct[tier or "M"]
    of_core = ms * settings.idle_fps / 10.0  # ms per frame x frames per second / 1000 x 100
    of_pc = of_core / cpus
    return {
        "megapixels": settings.idle_megapixels,
        "fps": settings.idle_fps,
        "frames": settings.idle_frames,
        "ms_per_frame": round(ms, 3),
        "cpu_pct_core": round(of_core, 2),  # of one core
        "cpu_pct": round(of_pc, 2),  # of the whole PC: what the limit is for
        "limit_pct": limit,
        "within_limit": of_pc <= limit,
    }


def classify(reference_ms: float, settings: BenchmarkSettings) -> Tier | None:
    if reference_ms <= settings.tier_r_max_ms:
        return "R"
    return "M" if reference_ms <= settings.tier_m_max_ms else None


def run_benchmark(
    settings: BenchmarkSettings | None = None,
    *,
    types: list[str] | None = None,
    clock: Callable[[], float] = time.perf_counter,
    cpu_clock: Callable[[], float] = time.process_time,
    idle: bool | None = None,
) -> dict[str, Any]:
    """Time the types (default: every registered one) at each size and build the report. The idle image trigger is timed with
    the full run, or when `idle` says so."""
    settings = settings or BenchmarkSettings()
    wanted = types if types is not None else registered()
    measured: list[dict[str, Any]] = []
    for item in wanted:
        if item in UNMEASURED or item not in WORKLOADS:
            continue
        kind, name, version = item.split(":")
        times = {}
        for mp in settings.megapixels:
            times[str(mp)] = round(_time(kind, name, int(version), WORKLOADS[item](mp), settings.repeats, clock), 3)
        measured.append({"type": item, "ms": times})
    reference = str(settings.reference_mp)
    reference_ms = sum(m["ms"][reference] for m in measured if m["type"].startswith("tool:"))
    tier = classify(reference_ms, settings)
    budgets = settings.budgets_ms[tier or "M"]
    for m in measured:
        budget = budgets.get(m["type"])
        m["budget_ms"] = budget
        m["within_budget"] = None if budget is None else m["ms"][reference] <= budget
    cpus = os.cpu_count() or 1
    caps = settings.thread_caps[tier or "M"]
    return {
        "format": 1,
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "host": {"cpus": cpus, "machine": platform.machine(), "system": platform.system(), "python": platform.python_version(), "opencv": cv2.__version__},
        "settings": {"megapixels": settings.megapixels, "repeats": settings.repeats, "reference_mp": settings.reference_mp},
        "reference_ms": round(reference_ms, 3),
        "tier": tier,  # None: slower than tier M
        "thread_limit": min(cpus, caps),  # proposed, not applied
        "measured": measured,
        "unmeasured": [{"type": k, "reason": r} for k, r in UNMEASURED.items() if k in wanted],
        "over_budget": [m["type"] for m in measured if m["within_budget"] is False],
        "idle_trigger": _idle_trigger(settings, tier, cpus, cpu_clock) if (types is None if idle is None else idle) else None,
    }


def report_path(root: Path | str) -> Path:
    return Path(root) / SYSTEM_DIR / REPORT_FILE


def save_report(root: Path | str, report: dict[str, Any]) -> Path:
    path = report_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{REPORT_FILE}.{uuid.uuid4().hex}")
    tmp.write_text(json.dumps(report, indent=2), encoding="utf-8")
    os.replace(tmp, path)
    return path


def load_report(root: Path | str) -> dict[str, Any] | None:
    path = report_path(root)
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def summary(report: dict[str, Any]) -> str:
    """The report as plain ASCII lines for the console."""
    tier = report["tier"] or "below M"
    lines = [f"Tier: {tier}  (reference workload {report['reference_ms']:.1f} ms at {report['settings']['reference_mp']} MP, {report['host']['cpus']} CPUs, thread limit {report['thread_limit']})"]
    for m in report["measured"]:
        times = "  ".join(f"{mp} MP {ms:7.1f} ms" for mp, ms in m["ms"].items())
        flag = "" if m["within_budget"] is not False else f"  OVER BUDGET ({m['budget_ms']} ms)"
        lines.append(f"  {m['type']:<22}{times}{flag}")
    idle = report.get("idle_trigger")
    if idle:
        verdict = "ok" if idle["within_limit"] else f"OVER THE LIMIT ({idle['limit_pct']:g} %)"
        lines.append(f"  image trigger waiting: {idle['ms_per_frame']:.1f} ms/frame at {idle['fps']:g} fps = {idle['cpu_pct']:.1f} % of the PC ({idle['cpu_pct_core']:.0f} % of a core), limit {idle['limit_pct']:g} %: {verdict}")
    lines += [f"  {u['type']:<22}not timed: {render(REASONS[u['reason']], 'en')}" for u in report["unmeasured"]]
    return "\n".join(lines)
