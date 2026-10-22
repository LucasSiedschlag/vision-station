"""Edge tool: where the gray level steps along a line, to a fraction of a pixel (FR-PLT-9, tier 1).

The region is a strip; the tool averages it across `direction` (`x`: it scans from left to right, so it finds vertical
edges; `y`: from top to bottom) and finds the edges of that profile with calipers (`algorithms/calipers.py`). `polarity`
is dark to light in the direction of the scan (`rising`), or the reverse (`falling`); `min_contrast` is the height of the
step in gray levels and `sigma` the smoothing in pixels. Distances are from the start of the strip. Four modes:

- **presence**: the number of edges, against `min_count` and `max_count`;
- **position**: the distance from the start of the strip to the first edge;
- **width**: from the first edge to the next one of the opposite polarity (a bar, a gap);
- **pitch**: between consecutive edges of the polarity of the first one (the teeth of a comb). `min_distance` is checked
  on the **smallest** gap and `max_distance` on the **largest**, so one tooth missing is a failure that a mean would hide.

- **diameter**: the diameter of a round feature (a hole, a pin, a cap) in the region. `rays` lines leave the centre of the
  region, the strongest edge of the `polarity` on each (`rising` is dark to light going **outwards**: a dark hole in a light
  plate is rising) between `ring_min` and `ring_max` of the reach of the region, and a circle is fitted through them; false
  edges far from the circle are dropped. The feature need not be at the centre, only around it. If too few rays find an edge,
  or the points are not round (their RMS distance to the circle over a tenth of its radius), it is **not found**: at least 70 % of the rays must find an edge that stays on the circle. `direction`
  does not matter.

A mode that needs edges it does not find (no first edge, no pair, fewer than two for a pitch) **fails** with the reason
`found`: a distance is never made up, so a job with only `max_distance` cannot pass a part that has no feature. Limits in
pixels (`min_distance`, `max_distance`) or in millimetres (`..._mm`) in a calibrated job (FR-INS-15).

Fields for `reason_fail`: {count} (the edges found), {distance} and {distance_mm} (the measure of the mode, in pixels
and, in a calibrated job, in millimetres; empty when it could not be measured), {distance_min}, {distance_max},
{distance_min_mm}, {distance_max_mm} (the smallest and largest gap of a pitch), {roundness} (diameter: the RMS distance of the edges to the circle, in pixels), {contrast} (the smallest contrast of the
edges used), the limits {min_count}, {max_count}, {min_distance}, {max_distance}, {min_distance_mm}, {max_distance_mm}.
"""

import math
from dataclasses import replace
from typing import Annotated, Literal, Self

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

from vision_station.algorithms.calipers import Edge, find_edges, fit_circle, profile, ray_profiles
from vision_station.algorithms.levels import gray_of
from vision_station.core.i18n import tr
from vision_station.core.jobfiles import JobFiles
from vision_station.core.results import MAX_MARKS, Criterion, Mark, Unit
from vision_station.core.schema_labels import labels, meta
from vision_station.tools.base import CriterionSpec, ToolError, ToolResult, ToolType, count_at_most, judged, maximum, minimum, register, rule

ARC_COVERAGE = 0.7  # diameter: the share of the rays that must find an edge that stays on the circle
ARC_ROUNDNESS = 0.1  # ...and the RMS distance of the edges to the circle, over its radius

Length = Annotated[float, Field(ge=0, allow_inf_nan=False)]


class EdgeParams(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra=labels(
        "Acha as bordas (degraus de brilho) ao longo de uma linha, com precisão de fração de pixel, e mede onde estão, a largura ou o passo.",
        meta={
            "mode": meta(1, "measure"),
            "direction": meta(1, "measure"),
            "polarity": meta(2, "measure"),
            "min_contrast": meta(2, "measure", unit="score"),
            "sigma": meta(3, "measure", unit="px"),
            "rays": meta(3, "measure"),
            "ring_min": meta(3, "measure", unit="fraction"),
            "ring_max": meta(3, "measure", unit="fraction"),
            "min_count": meta(1, "criteria", unit="count", tunable=True),
            "max_count": meta(1, "criteria", unit="count", tunable=True),
            "min_distance": meta(1, "criteria", unit="px", tunable=True),
            "max_distance": meta(1, "criteria", unit="px", tunable=True),
            "min_distance_mm": meta(2, "criteria", unit="mm", tunable=True),
            "max_distance_mm": meta(2, "criteria", unit="mm", tunable=True),
        },
        mode=("Medir", "", {"presence": "quantas bordas", "position": "a posição da primeira borda", "width": "a largura (entre duas bordas)", "pitch": "o passo (entre bordas repetidas)", "diameter": "o diâmetro de uma peça redonda"}),
        direction=("Varrer na direção", "x: da esquerda para a direita (acha bordas verticais); y: de cima para baixo", {"x": "horizontal (x)", "y": "vertical (y)"}),
        polarity=("Tipo de borda", "Subida: do escuro para o claro na direção da varredura", {"any": "qualquer", "rising": "subida (escuro→claro)", "falling": "descida (claro→escuro)"}),
        min_contrast=("Contraste mínimo", "Altura do degrau em níveis de cinza (0 a 255)"),
        sigma=("Suavização (px)", "Quanto o perfil é suavizado antes de achar as bordas; pelo menos 0,5"),
        rays=("Raios", "Diâmetro: quantas linhas saem do centro da região para achar a borda"),
        ring_min=("Começo da busca", "Diâmetro: fração do alcance (do centro à borda da região) onde a busca começa"),
        ring_max=("Fim da busca", "Diâmetro: fração do alcance onde a busca termina"),
        min_count=("Mínimo de bordas", ""),
        max_count=("Máximo de bordas", ""),
        min_distance=("Distância mínima (px)", "Posição, largura ou passo, conforme o modo; no passo vale para o menor intervalo"),
        max_distance=("Distância máxima (px)", "No passo vale para o maior intervalo"),
        min_distance_mm=("Distância mínima (mm)", "Precisa da calibração do job"),
        max_distance_mm=("Distância máxima (mm)", "Precisa da calibração do job"),
    ))

    mode: Literal["presence", "position", "width", "pitch", "diameter"]
    direction: Literal["x", "y"] = "x"
    polarity: Literal["any", "rising", "falling"] = "any"
    min_contrast: Annotated[float, Field(ge=1, le=255)] = 20
    sigma: Annotated[float, Field(ge=0.5, le=20)] = 1.0
    rays: Annotated[int, Field(ge=8, le=360)] = 36  # diameter: how many rays from the centre
    ring_min: Annotated[float, Field(ge=0, lt=1)] = 0.1  # diameter: where the search starts and ends, as fractions of the reach of the region
    ring_max: Annotated[float, Field(gt=0, le=1)] = 1.0
    min_count: Annotated[int, Field(ge=0)] | None = None
    max_count: Annotated[int, Field(ge=0)] | None = None
    min_distance: Length | None = None
    max_distance: Length | None = None
    min_distance_mm: Length | None = None
    max_distance_mm: Length | None = None

    @model_validator(mode="after")
    def _valid(self) -> Self:
        distances = (self.min_distance, self.max_distance, self.min_distance_mm, self.max_distance_mm)
        if self.mode == "presence" and self.min_count is None and self.max_count is None:
            raise ValueError("mode 'presence' needs min_count or max_count")
        if self.mode != "presence" and all(v is None for v in distances):
            raise ValueError(f"mode '{self.mode}' needs a limit on the distance: min_distance, max_distance or the ones in mm")
        if self.ring_min >= self.ring_max:
            raise ValueError("ring_min must be below ring_max")
        for low, high in ((self.min_count, self.max_count), (self.min_distance, self.max_distance), (self.min_distance_mm, self.max_distance_mm)):
            if low is not None and high is not None and low > high:
                raise ValueError("a minimum must not be above its maximum")
        return self


def _measure(edges: list[Edge], mode: str) -> tuple[list[Edge], dict[str, float] | None]:
    """The edges the mode uses and its measure(s), or None when the edges it needs are not there."""
    if mode == "presence":
        return edges, {}
    if not edges:
        return [], None
    first = edges[0]
    if mode == "position":
        d = first.position + 0.5  # from the start of the strip, whose first pixel begins at -0.5
        return [first], {"distance": d, "min": d, "max": d}
    if mode == "width":
        partner = next((e for e in edges[1:] if e.rising != first.rising), None)
        if partner is None:
            return [], None
        d = partner.position - first.position
        return [first, partner], {"distance": d, "min": d, "max": d}
    same = [e for e in edges if e.rising == first.rising]  # pitch: the polarity of the first edge, else it would be half a period
    if len(same) < 2:
        return [], None
    gaps = np.diff([e.position for e in same])
    return same, {"distance": float(gaps.mean()), "min": float(gaps.min()), "max": float(gaps.max())}


class _Measured:
    """What a mode found: the edges it used, its measure(s) or None when the edges it needs are not there, and what to draw."""

    def __init__(self, count: int, measures: dict[str, float] | None, marks: list[Mark], contrast: float | None, extra: dict[str, float], top: float, mm: float | None):
        self.count, self.measures, self.marks, self.contrast, self.extra, self.top, self.mm = count, measures, marks, contrast, extra, top, mm


def _line(region: np.ndarray, params: EdgeParams, files: JobFiles) -> _Measured:
    height, width = region.shape[:2]
    length = float(width if params.direction == "x" else height)
    edges = find_edges(profile(region, params.direction), params.sigma, params.polarity, params.min_contrast)
    used, measures = _measure(edges, params.mode)
    across = float(height - 1 if params.direction == "x" else width - 1)
    marks: list[Mark] = []
    for e in used[: MAX_MARKS - 1]:  # a line across the strip at each edge used
        line = ((e.position, 0.0), (e.position, across)) if params.direction == "x" else ((0.0, e.position), (across, e.position))
        marks.append(Mark("poly", "found", line, closed=False))
    scale = _scale(params, files)
    mm = None if scale is None else (scale.x if params.direction == "x" else scale.y)  # square pixels; see the reference
    if params.mode in ("width", "pitch") and measures and len(used) >= 2:
        mid = (used[0].position + used[1].position) / 2
        at = (mid, min(12.0, across)) if params.direction == "x" else (min(2.0, float(width - 1)), mid)
        shown = measures["distance"] if mm is None else measures["distance"] * mm
        marks.append(Mark("text", "found", (at,), text=f"{shown:.1f} {'px' if mm is None else 'mm'}"))
    return _Measured(len(edges), measures, marks, min((e.contrast for e in used), default=None), {}, length, mm)


def _arc(region: np.ndarray, params: EdgeParams, files: JobFiles) -> _Measured:
    """The diameter of a round feature: rays from the centre of the region, the strongest edge of the polarity on each, and a circle
    through them. It is not found when fewer than `ARC_COVERAGE` of the rays have an edge on the circle or the points are not round
    (their RMS distance to the circle over `ARC_ROUNDNESS` of its radius)."""
    height, width = region.shape[:2]
    centre = ((width - 1) / 2, (height - 1) / 2)
    reach = min(width, height) / 2 - 1  # the longest ray that stays in the region
    r0, r1 = params.ring_min * reach, params.ring_max * reach
    scale = _scale(params, files)
    mm = None if scale is None else scale.mean  # a circle is the same in every direction only with square pixels
    if r1 - r0 < 4:
        return _Measured(0, None, [], None, {}, 2 * reach, mm)
    angles = np.linspace(0, 2 * np.pi, params.rays, endpoint=False)
    points, contrasts = [], []
    for angle, ray in zip(angles, ray_profiles(gray_of(region), centre, (r0, r1), angles), strict=True):
        found = find_edges(ray, params.sigma, params.polarity, params.min_contrast)
        if found:
            best = max(found, key=lambda e: e.contrast)
            radius = r0 + best.position
            points.append((centre[0] + radius * np.cos(angle), centre[1] + radius * np.sin(angle)))
            contrasts.append(best.contrast)
    enough = max(5, math.ceil(ARC_COVERAGE * params.rays))
    fit = fit_circle(np.array(points)) if len(points) >= enough else None
    if fit is None or fit[3] > ARC_ROUNDNESS * fit[2] or fit[4].sum() < enough:
        return _Measured(len(points), None, [], None, {}, 2 * reach, mm)
    cx, cy, radius, rms, kept = fit
    diameter = 2 * radius
    ring = tuple((float(cx + radius * np.cos(t)), float(cy + radius * np.sin(t))) for t in np.linspace(0, 2 * np.pi, 48, endpoint=False))
    marks = [Mark("poly", "found", ring), Mark("point", "found", ((float(cx), float(cy)),)),
             Mark("text", "found", ((float(cx), float(cy)),), text=f"Ø {diameter if mm is None else diameter * mm:.1f} {'px' if mm is None else 'mm'}")]
    contrast = min(c for c, k in zip(contrasts, kept, strict=True) if k)
    return _Measured(int(kept.sum()), {"distance": diameter, "min": diameter, "max": diameter}, marks, contrast, {"roundness": rms}, 2 * reach, mm)


def _scale(params: EdgeParams, files: JobFiles):
    needs_mm = params.min_distance_mm is not None or params.max_distance_mm is not None
    return files.scale() if needs_mm or files.calibrated else None


def run(region: np.ndarray, params: EdgeParams, files: JobFiles) -> ToolResult:
    if region.size == 0:
        raise ToolError("the region is empty")
    found = _arc(region, params, files) if params.mode == "diameter" else _line(region, params, files)
    measures, mm, top = found.measures, found.mm, found.top
    values: dict = {"count": found.count, "distance": None, "distance_mm": None, "distance_min": None, "distance_max": None, "distance_min_mm": None,
                    "distance_max_mm": None, "contrast": found.contrast, "roundness": None, "min_count": params.min_count, "max_count": params.max_count,
                    "min_distance": params.min_distance, "max_distance": params.max_distance, "min_distance_mm": params.min_distance_mm, "max_distance_mm": params.max_distance_mm}
    units: dict[str, Unit] = {"count": "count"}
    criteria: list[Criterion] = []
    if params.min_count is not None:
        criteria.append(minimum("min_count", "count", found.count, params.min_count))
    if params.max_count is not None:
        criteria.append(count_at_most("max_count", "count", found.count, params.max_count))
    if params.mode != "presence":
        criteria.append(rule("found", 0.0 if measures is None else 1.0))  # a distance is never made up
    if measures:
        for key, name in (("distance", "distance"), ("min", "distance_min"), ("max", "distance_max")):
            values[name] = measures[key]
            units[name] = "px"
            if mm is not None:
                values[f"{name}_mm"] = measures[key] * mm
                units[f"{name}_mm"] = "mm"
        for name, number in found.extra.items():
            values[name] = number
            units[name] = "px"
        # a pitch is judged on every gap: the smallest against the minimum and the largest against the maximum
        low, high = ("min", "max") if params.mode == "pitch" else ("distance", "distance")
        lo_name, hi_name = ("distance_min", "distance_max") if params.mode == "pitch" else ("distance", "distance")
        if params.min_distance is not None:
            criteria.append(minimum("min_distance", lo_name, measures[low], params.min_distance))
        if params.max_distance is not None:
            criteria.append(maximum("max_distance", hi_name, measures[high], params.max_distance, top))
        if mm is not None:
            if params.min_distance_mm is not None:
                criteria.append(minimum("min_distance_mm", f"{lo_name}_mm", measures[low] * mm, params.min_distance_mm))
            if params.max_distance_mm is not None:
                criteria.append(maximum("max_distance_mm", f"{hi_name}_mm", measures[high] * mm, params.max_distance_mm, top * mm))
    role = "defect" if any(c.code.startswith("max_") and not c.passed for c in criteria) else "found"
    marks = tuple(replace(m, role=role) for m in found.marks[:MAX_MARKS])
    return judged(criteria, values=values, details={"count": found.count}, units=units, marks=marks)


EDGE = register(ToolType(
    name="edge", version=1, params=EdgeParams, run=run,
    criteria=(
        CriterionSpec("count", tr("Bordas"), "count", "min_count", "max_count"),
        CriterionSpec("distance", tr("Distância entre bordas"), "px", "min_distance", "max_distance"),
        CriterionSpec("distance_min", tr("Menor intervalo (passo)"), "px", "min_distance", None, level=3),
        CriterionSpec("distance_max", tr("Maior intervalo (passo)"), "px", None, "max_distance", level=3),
        CriterionSpec("distance_mm", tr("Distância entre bordas (mm)"), "mm", "min_distance_mm", "max_distance_mm", level=2),
    ),
))
