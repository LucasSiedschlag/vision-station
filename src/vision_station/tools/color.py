"""Color tool: how much of a region has a color (FR-INS-2, TD-19).

The region is the validation area the user draws. The color is a range in HSV or a reference color with
a distance (see `vision_station.colors`). A hue range needs a saturation limit (`s_min`): grays and whites
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
from pydantic import Field, model_validator

from vision_station.colors import ColorRange, color_mask
from vision_station.jobfiles import JobFiles
from vision_station.tools.base import ToolResult, ToolType, register

Share = Annotated[float, Field(ge=0, le=1)]


class ColorParams(ColorRange):
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


def _longest_run(flags: np.ndarray) -> tuple[int, int]:
    """Start and length of the longest run of True."""
    best_start, best_len, start = 0, 0, None
    for i, f in enumerate(np.append(flags, False)):
        if f and start is None:
            start = i
        elif not f and start is not None:
            if i - start > best_len:
                best_start, best_len = start, i - start
            start = None
    return best_start, best_len


def _at_least(value: float, limit: float) -> float:
    return 1.0 if value >= limit else (value / limit if limit > 0 else 1.0)


def _at_most(value: float, limit: float) -> float:
    return 1.0 if value <= limit else max(0.0, (1 - value) / (1 - limit)) if limit < 1 else 1.0


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
        scores.append(_at_least(fraction, params.min_fraction))
    if params.max_fraction is not None:
        scores.append(_at_most(fraction, params.max_fraction))
    if params.axis != "none":
        per_line = mask.mean(axis=0 if params.axis == "x" else 1) if mask.size else np.zeros(0)
        covered = per_line >= params.line_min
        length = len(covered)
        coverage = float(covered.mean()) if length else 0.0
        gap_start, gap_len = _longest_run(~covered)
        gap = gap_len / length if length else 1.0
        values.update(coverage=coverage, missing=1.0 - coverage, gap=gap)
        details.update(axis=params.axis, coverage=coverage, gap=gap, gap_at=[gap_start / length, (gap_start + gap_len) / length] if gap_len else None)
        if params.min_coverage is not None:
            scores.append(_at_least(coverage, params.min_coverage))
        if params.max_gap is not None:
            scores.append(_at_most(gap, params.max_gap))
    score = min(scores)
    return ToolResult(passed=score >= 1.0, score=score, values=values, details=details)


COLOR = register(ToolType(name="color", version=1, params=ColorParams, run=run))
