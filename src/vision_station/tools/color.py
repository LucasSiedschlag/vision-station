"""Color tool: how much of a region has a color (FR-INS-2, TD-19).

The region is the validation area the user draws. The color is a range in HSV or a reference color with
a distance (see `vision_station.algorithms.color`). A hue range needs a saturation limit (`s_min`): grays and whites
have hue 0, which is red. Two ways to judge it, which can be combined:

- **area**: the fraction of the region's pixels in the color (`min_fraction`, `max_fraction`). E.g. a
  colored cap is present; no red where there should be none.
- **along an axis** (`axis: x` or `y`): the region is a strip; a column (or row) is covered when at least
  `line_min` of it has the color. `min_coverage` is the covered fraction of the length and `max_gap` the
  longest uncovered stretch. E.g. a colored band or tape runs the whole length of a seam.

Fields for `reason_fail`: {fraction}, {coverage}, {missing} (1 - coverage), {gap}, as fractions
(format them with `:.0%`), and the limits {min_fraction}, {max_fraction}, {min_coverage}, {max_gap}.
"""

from typing import Annotated, Literal, Self

import numpy as np
from pydantic import ConfigDict, Field, model_validator

from vision_station.algorithms.color import ColorRange, color_mask
from vision_station.core.schema_labels import COLOR_RANGE, labels
from vision_station.core.jobfiles import JobFiles
from vision_station.tools.base import ToolResult, ToolType, register
from vision_station.algorithms.measures import at_least, at_most, strip_profile

Share = Annotated[float, Field(ge=0, le=1)]


class ColorParams(ColorRange):
    model_config = ConfigDict(extra="forbid", json_schema_extra=labels(
        "Mede quanto de uma região tem uma cor.",
        **COLOR_RANGE,
        min_fraction=("Fração mínima da área", "0 a 1: a cor precisa ocupar pelo menos isso da região"),
        max_fraction=("Fração máxima da área", "0 a 1: para conferir que uma cor não está lá"),
    axis=("Medir ao longo de", "Área toda, ou a cobertura ao longo de uma faixa horizontal (x) ou vertical (y)", {"none": "área toda", "x": "horizontal (x)", "y": "vertical (y)"}),
    min_coverage=("Cobertura mínima", "0 a 1: parte do comprimento que precisa estar coberta"),
    max_gap=("Maior trecho faltando", "0 a 1 do comprimento, pontas incluídas"),
        line_min=("Mínimo por coluna (ou linha)", "0 a 1: parte de cada coluna com a cor para ela contar como coberta"),
    ))

    min_fraction: Share | None = None
    max_fraction: Share | None = None
    axis: Literal["none", "x", "y"] = "none"
    line_min: Annotated[float, Field(gt=0, le=1)] = 0.3
    min_coverage: Share | None = None
    max_gap: Share | None = None

    @model_validator(mode="after")
    def _criteria(self) -> Self:
        if self.min_fraction is None and self.max_fraction is None and self.min_coverage is None and self.max_gap is None:
            raise ValueError("give at least one of min_fraction, max_fraction, min_coverage, max_gap")
        if self.axis == "none" and (self.min_coverage is not None or self.max_gap is not None):
            raise ValueError("min_coverage and max_gap need axis 'x' or 'y'")
        if self.min_fraction is not None and self.max_fraction is not None and self.min_fraction > self.max_fraction:
            raise ValueError("min_fraction must not be above max_fraction")
        return self








def run(region: np.ndarray, params: ColorParams, files: JobFiles) -> ToolResult:
    mask = color_mask(region, params) if region.size else np.zeros((0, 0), bool)
    fraction = float(mask.mean()) if mask.size else 0.0
    values: dict = {
        "fraction": fraction,
        "min_fraction": params.min_fraction,
        "max_fraction": params.max_fraction,
        "min_coverage": params.min_coverage,
        "max_gap": params.max_gap,
    }
    details: dict = {"fraction": fraction}
    scores: list[float] = []
    if params.min_fraction is not None:
        scores.append(at_least(fraction, params.min_fraction))
    if params.max_fraction is not None:
        scores.append(at_most(fraction, params.max_fraction))
    if params.axis != "none":
        per_line = mask.mean(axis=0 if params.axis == "x" else 1) if mask.size else np.zeros(0)
        profile = strip_profile(per_line >= params.line_min)
        coverage, gap = profile["coverage"], profile["gap"]
        values.update(coverage=coverage, missing=1.0 - coverage, gap=gap)
        details.update(axis=params.axis, **profile)
        if params.min_coverage is not None:
            scores.append(at_least(coverage, params.min_coverage))
        if params.max_gap is not None:
            scores.append(at_most(gap, params.max_gap))
    score = min(scores)
    return ToolResult(passed=score >= 1.0, score=score, values=values, details=details)


COLOR = register(ToolType(name="color", version=1, params=ColorParams, run=run))
