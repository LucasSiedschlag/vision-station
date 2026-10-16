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

Fields for `reason_fail`: {count}, {min_count}, {max_count}, {best} (best score), {coverage}, {missing}
(1 - coverage), {gap}, {min_coverage}, {max_gap}; fractions format with `:.0%`.
"""

from typing import Annotated, Literal, Self

import cv2
import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

from vision_station.jobfiles import JobFiles
from vision_station.schema_labels import labels
from vision_station.tools.base import ToolError, ToolResult, ToolType, register
from vision_station.tools.measures import at_least, at_most, strip_profile

Share = Annotated[float, Field(ge=0, le=1)]
MAX_MATCHES = 500


class PatternParams(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra=labels(
        "Procura um padrão ensinado (um logotipo, uma marca, um detalhe) numa região e conta quantas vezes aparece.",
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








def run(region: np.ndarray, params: PatternParams, files: JobFiles) -> ToolResult:
    template = files.image(params.template, gray=True)
    if float(template.std()) < 1.0:
        raise ToolError(f"template {params.template} is flat: nothing to match")
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
    scores = [at_least(count, params.min_count)]
    if params.max_count is not None and count > params.max_count:
        scores.append(0.0)
    if params.axis != "none":
        length = gray.shape[1] if params.axis == "x" else gray.shape[0]
        covered = np.zeros(length, bool)
        for x, y, _ in matches:
            start, size = (x, tw) if params.axis == "x" else (y, th)
            covered[start : start + size] = True
        profile = strip_profile(covered)
        coverage, gap = profile["coverage"], profile["gap"]
        values.update(coverage=coverage, missing=1.0 - coverage, gap=gap)
        details.update(axis=params.axis, **profile)
        if params.min_coverage is not None:
            scores.append(at_least(coverage, params.min_coverage))
        if params.max_gap is not None:
            scores.append(at_most(gap, params.max_gap))
    score = min(scores)
    return ToolResult(passed=score >= 1.0, score=score, values=values, details=details)


PATTERN = register(ToolType(name="pattern", version=1, params=PatternParams, run=run, needs=lambda p: [p.template]))
