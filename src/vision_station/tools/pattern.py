"""Pattern tool: finds a taught template (a logo, a mark, a feature) in a region and counts it (FR-INS-3, TD-19).

The template is an image inside the job (e.g. `patterns/logo.png`), cut from the reference image, so it has
the frame's scale. Matching is normalized correlation on gray levels (OpenCV TM_CCOEFF_NORMED): it tolerates
changes of brightness and contrast, not a rotation or a change of size. Every place scoring at least
`min_score` counts once (overlapping matches are merged).

Two ways to judge, which can be combined:

- **count**: `min_count` (default 1: "the pattern is there") and `max_count`.
- **along an axis** (`axis: x` or `y`): the region is a strip and each match covers its own length of it.
  `min_coverage` is the covered fraction of the length and `max_gap` the longest stretch without the
  pattern, ends included. E.g. a printed logo repeats along the whole seam; a short or missing tape
  leaves a gap.

**v2** matches by the direction of the edges of the template instead of correlating gray levels (`algorithms/shapematch.py`):
it finds the pattern **turned** (`angles`) and **larger or smaller** (`scales`), whatever the brightness, and with part of it
hidden (the score falls by the share hidden). `min_score` is then the score of that match; the count and the coverage are judged
as in v1, a match covering the length of its turned and scaled box along the axis. The whole pattern must be inside the region
(a template larger than the region is a refusal). `pattern` v1 stays for the jobs that were saved with it.

Fields for `reason_fail`: {count}, {min_count}, {max_count}, {best} (best score), {coverage}, {missing}
(1 - coverage), {gap}, {min_coverage}, {max_gap}; fractions format with `:.0%`.
"""

from typing import Annotated, Literal, Self

import cv2
import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

from vision_station.core.jobfiles import JobFiles
from vision_station.core.i18n import tr
from vision_station.core.schema_labels import labels, meta
from vision_station.algorithms.measures import strip_profile
from vision_station.algorithms.shapematch import find_shapes, model_from_png
from vision_station.core.results import MAX_MARKS, Mark, Unit
from vision_station.tools.base import CriterionSpec, ToolError, ToolResult, ToolType, count_at_most, judged, maximum, minimum, register

Share = Annotated[float, Field(ge=0, le=1)]
MAX_MATCHES = 500


class PatternParams(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra=labels(
        "Procura um padrão ensinado (um logotipo, uma marca, um detalhe) numa região e conta quantas vezes aparece.",
        meta={
            "template": meta(1, "measure", widget="template"),
            "min_score": meta(1, "criteria", unit="score", tunable=True),
            "min_count": meta(1, "criteria", unit="count", tunable=True),
            "max_count": meta(1, "criteria", unit="count", tunable=True),
            "axis": meta(2, "measure"),
            "min_coverage": meta(2, "criteria", unit="fraction", tunable=True),
            "max_gap": meta(2, "criteria", unit="fraction", tunable=True),
            "max_side": meta(3, "measure", unit="px"),
        },
        template=("Gabarito", "Imagem dentro do job, recortada da imagem de referência"),
        min_score=("Semelhança mínima", "0 a 1; 0,7 é um bom começo"),
        min_count=("Mínimo de ocorrências", "1: o padrão precisa estar lá; 0: com máximo 0, confere que não está"),
        max_count=("Máximo de ocorrências", "Vazio: sem limite"),
    axis=("Medir ao longo de", "Área toda, ou a cobertura ao longo de uma faixa horizontal (x) ou vertical (y)", {"none": "área toda", "x": "horizontal (x)", "y": "vertical (y)"}),
    min_coverage=("Cobertura mínima", "0 a 1: parte do comprimento que precisa estar coberta"),
    max_gap=("Maior trecho faltando", "0 a 1 do comprimento, pontas incluídas"),
        max_side=("Maior lado para comparar (px)", "Regiões maiores são reduzidas para comparar mais rápido"),
    ))

    template: Annotated[str, Field(min_length=1)]  # image inside the job
    min_score: Annotated[float, Field(gt=0, le=1)] = 0.7
    min_count: Annotated[int, Field(ge=0)] = 1
    max_count: Annotated[int, Field(ge=0)] | None = None
    axis: Literal["none", "x", "y"] = "none"
    min_coverage: Share | None = None
    max_gap: Share | None = None
    max_side: Annotated[int, Field(ge=64, le=4096)] = 1024  # a larger region is matched smaller, for speed

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if self.axis == "none" and (self.min_coverage is not None or self.max_gap is not None):
            raise ValueError("min_coverage and max_gap need axis 'x' or 'y'")
        if self.max_count is not None and self.max_count < self.min_count:
            raise ValueError("max_count must not be lower than min_count")
        return self


def _gray(image: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image


def find_matches(region: np.ndarray, template: np.ndarray, min_score: float) -> list[tuple[int, int, float]]:
    """Top-left corners (x, y) and scores of every match, best first; a match hides the others it overlaps
    by more than half the template."""
    result = np.nan_to_num(cv2.matchTemplate(region, template, cv2.TM_CCOEFF_NORMED), nan=-1.0)
    th, tw = template.shape
    found: list[tuple[int, int, float]] = []
    while len(found) < MAX_MATCHES:
        _, best, _, (x, y) = cv2.minMaxLoc(result)
        if best < min_score:
            break
        found.append((x, y, float(best)))
        result[max(0, y - th // 2) : y + th // 2 + 1, max(0, x - tw // 2) : x + tw // 2 + 1] = -1.0
    return found








def _covered(matches: list[tuple[int, int, float]], tw: int, th: int, axis: str, shape: tuple[int, ...]) -> np.ndarray:
    """Which positions along `axis` a match covers, for the matches of v1 (each covers the length of the template)."""
    covered = np.zeros(shape[1] if axis == "x" else shape[0], bool)
    for x, y, _ in matches:
        start, size = (x, tw) if axis == "x" else (y, th)
        covered[start : start + size] = True
    return covered


def _judge_count_and_coverage(params, count: int, best: float, values: dict, details: dict, covered: np.ndarray | None):
    """The criteria of both versions: the count against `min_count` and `max_count`, and, along an axis, the coverage and the longest
    gap. Adds the measures to `values` and `details`; returns the criteria and the units of the measures."""
    criteria = [minimum("min_count", "count", count, params.min_count)]
    if params.max_count is not None:
        criteria.append(count_at_most("max_count", "count", count, params.max_count))
    units: dict[str, Unit] = {"count": "count", "best": "score"}
    if covered is not None:
        profile = strip_profile(covered)
        coverage, gap = profile["coverage"], profile["gap"]
        values.update(coverage=coverage, missing=1.0 - coverage, gap=gap)
        details.update(axis=params.axis, **profile)
        units.update(coverage="fraction", missing="fraction", gap="fraction")
        if params.min_coverage is not None:
            criteria.append(minimum("min_coverage", "coverage", coverage, params.min_coverage))
        if params.max_gap is not None:
            criteria.append(maximum("max_gap", "gap", gap, params.max_gap))
    return criteria, units


def run(region: np.ndarray, params: PatternParams, files: JobFiles) -> ToolResult:
    template = files.image(params.template, gray=True)
    if float(template.std()) < 1.0:
        raise ToolError(f"template {params.template} is flat: nothing to match")
    if region.size == 0:
        raise ToolError("the region is empty")
    gray = _gray(region)
    scale = min(1.0, params.max_side / max(gray.shape[:2] or (1,)))
    if scale < 1.0:
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        template = cv2.resize(template, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    th, tw = template.shape
    if th > gray.shape[0] or tw > gray.shape[1]:
        raise ToolError(f"template {params.template} ({tw}x{th}) is larger than the region ({gray.shape[1]}x{gray.shape[0]})")

    matches = find_matches(gray, template, params.min_score)
    count = len(matches)
    best = max((s for _, _, s in matches), default=0.0)
    values: dict = {"count": count, "min_count": params.min_count, "max_count": params.max_count, "best": best,
                    "min_coverage": params.min_coverage, "max_gap": params.max_gap}
    details: dict = {
        "count": count,
        "matches": [{"rect": [round(x / scale), round(y / scale), round((x + tw) / scale), round((y + th) / scale)], "score": s} for x, y, s in matches],
    }
    criteria, units = _judge_count_and_coverage(params, count, best, values, details, _covered(matches, tw, th, params.axis, gray.shape) if params.axis != "none" else None)
    height, width = region.shape[:2]
    role = "defect" if any(c.code == "max_count" and not c.passed for c in criteria) else "found"  # more than allowed
    marks = tuple(
        Mark("rect", role, ((min(x / scale, width), min(y / scale, height)), (min((x + tw) / scale, width), min((y + th) / scale, height))))
        for x, y, _ in matches[:MAX_MARKS]  # best first
    )
    return judged(criteria, values=values, details=details, units=units, marks=marks)


class PatternParamsV2(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra=labels(
        "Procura um padrão ensinado pelo contorno, girado e em outro tamanho, e conta quantas vezes aparece.",
        meta={
            "template": meta(1, "measure", widget="template"),
            "angles": meta(1, "measure"),
            "scales": meta(2, "measure"),
            "polarity": meta(3, "measure"),
            "min_score": meta(1, "criteria", unit="score", tunable=True),
            "min_count": meta(1, "criteria", unit="count", tunable=True),
            "max_count": meta(1, "criteria", unit="count", tunable=True),
            "axis": meta(2, "measure"),
            "min_coverage": meta(2, "criteria", unit="fraction", tunable=True),
            "max_gap": meta(2, "criteria", unit="fraction", tunable=True),
            "max_instances": meta(3, "measure", unit="count"),
        },
        template=("Gabarito", "Imagem dentro do job, recortada da imagem de referência"),
        angles=("Ângulos (de, até)", "Graus; quanto o padrão pode estar girado em relação ao ensinado. Quanto menor a faixa, mais rápido"),
        scales=("Tamanhos (de, até)", "1 é o tamanho ensinado; 0,9 a 1,1 aceita 10% menor ou maior"),
        polarity=("Claro e escuro", "Se o padrão pode aparecer com o claro e o escuro trocados", {"same": "como ensinado", "ignore": "aceitar trocados"}),
        min_score=("Semelhança mínima", "0 a 1; 0,7 é um bom começo"),
        min_count=("Mínimo de ocorrências", "1: o padrão precisa estar lá; 0: com máximo 0, confere que não está"),
        max_count=("Máximo de ocorrências", "Vazio: sem limite"),
        axis=("Medir ao longo de", "Área toda, ou a cobertura ao longo de uma faixa horizontal (x) ou vertical (y)", {"none": "área toda", "x": "horizontal (x)", "y": "vertical (y)"}),
        min_coverage=("Cobertura mínima", "0 a 1: parte do comprimento que precisa estar coberta"),
        max_gap=("Maior trecho faltando", "0 a 1 do comprimento, pontas incluídas"),
        max_instances=("Máximo de ocorrências procuradas", "Para de procurar depois de tantas; contar mais que isso não é possível"),
    ))

    template: Annotated[str, Field(min_length=1)]  # image inside the job
    angles: tuple[Annotated[float, Field(ge=-180, le=180)], Annotated[float, Field(ge=-180, le=180)]] = (-20.0, 20.0)
    scales: tuple[Annotated[float, Field(gt=0, le=4)], Annotated[float, Field(gt=0, le=4)]] = (0.9, 1.1)
    polarity: Literal["same", "ignore"] = "same"
    min_score: Annotated[float, Field(gt=0, le=1)] = 0.7
    min_count: Annotated[int, Field(ge=0)] = 1
    max_count: Annotated[int, Field(ge=0)] | None = None
    axis: Literal["none", "x", "y"] = "none"
    min_coverage: Share | None = None
    max_gap: Share | None = None
    max_instances: Annotated[int, Field(ge=1, le=200)] = 50

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if self.axis == "none" and (self.min_coverage is not None or self.max_gap is not None):
            raise ValueError("min_coverage and max_gap need axis 'x' or 'y'")
        if self.max_count is not None and self.max_count < self.min_count:
            raise ValueError("max_count must not be lower than min_count")
        if self.angles[0] > self.angles[1] or self.scales[0] > self.scales[1]:
            raise ValueError("angles and scales are ranges, low to high")
        return self


def run_v2(region: np.ndarray, params: PatternParamsV2, files: JobFiles) -> ToolResult:
    try:
        model = model_from_png(files.bytes(params.template))
    except ValueError as exc:
        raise ToolError(f"template {params.template}: {exc}") from exc
    if region.size == 0:
        raise ToolError("the region is empty")
    height, width = region.shape[:2]
    tw, th = model.size
    if th > height or tw > width:
        raise ToolError(f"template {params.template} ({tw}x{th}) is larger than the region ({width}x{height})")
    try:
        matches = find_shapes(region, model, angles=params.angles, scales=params.scales, min_score=params.min_score,
                              max_instances=params.max_instances, polarity=params.polarity)
    except ValueError as exc:
        raise ToolError(str(exc)) from exc
    count = len(matches)
    best = max((m.score for m in matches), default=0.0)
    values: dict = {"count": count, "min_count": params.min_count, "max_count": params.max_count, "best": best,
                    "min_coverage": params.min_coverage, "max_gap": params.max_gap}
    boxes = [_box(m, tw, th, width, height) for m in matches]  # the corners of each match, turned and scaled, in the region
    details: dict = {
        "count": count,
        "matches": [{"x": m.x, "y": m.y, "angle": m.angle, "scale": m.scale, "score": m.score, "corners": b.tolist()} for m, b in zip(matches, boxes, strict=True)],
    }
    covered = None
    if params.axis != "none":
        covered = np.zeros(width if params.axis == "x" else height, bool)
        for b in boxes:  # a match covers the stretch of the axis its turned box spans
            lo, hi = (b[:, 0].min(), b[:, 0].max()) if params.axis == "x" else (b[:, 1].min(), b[:, 1].max())
            covered[max(0, int(np.floor(lo + 0.5))) : max(0, int(np.ceil(hi + 0.5)))] = True
    criteria, units = _judge_count_and_coverage(params, count, best, values, details, covered)
    role = "defect" if any(c.code == "max_count" and not c.passed for c in criteria) else "found"  # more than allowed
    marks = tuple(Mark("poly", role, tuple((float(x), float(y)) for x, y in b)) for b in boxes[:MAX_MARKS])  # best first
    return judged(criteria, values=values, details=details, units=units, marks=marks)


def _box(match, tw: int, th: int, width: int, height: int) -> np.ndarray:
    """The four corners of the template as it was found (turned and scaled about its centre), clipped to the region."""
    a = np.radians(match.angle)
    c, s = np.cos(a), np.sin(a)
    half = np.array([[-tw / 2, -th / 2], [tw / 2, -th / 2], [tw / 2, th / 2], [-tw / 2, th / 2]]) * match.scale
    corners = np.column_stack([half[:, 0] * c + half[:, 1] * s, -half[:, 0] * s + half[:, 1] * c]) + (match.x, match.y)
    return np.clip(corners, [0.0, 0.0], [float(width), float(height)])


PATTERN = register(ToolType(
    name="pattern", version=1, params=PatternParams, run=run, needs=lambda p: [p.template],
    criteria=(
        CriterionSpec("count", tr("Ocorrências do padrão"), "count", "min_count", "max_count"),
        CriterionSpec("coverage", tr("Cobertura da faixa"), "fraction", "min_coverage", None, (0.0, 1.0), level=2),
        CriterionSpec("gap", tr("Maior trecho faltando"), "fraction", None, "max_gap", (0.0, 1.0), level=2),
    ),
))

PATTERN_V2 = register(ToolType(
    name="pattern", version=2, params=PatternParamsV2, run=run_v2, needs=lambda p: [p.template],
    criteria=(
        CriterionSpec("count", tr("Ocorrências do padrão"), "count", "min_count", "max_count"),
        CriterionSpec("coverage", tr("Cobertura da faixa"), "fraction", "min_coverage", None, (0.0, 1.0), level=2),
        CriterionSpec("gap", tr("Maior trecho faltando"), "fraction", None, "max_gap", (0.0, 1.0), level=2),
    ),
))
