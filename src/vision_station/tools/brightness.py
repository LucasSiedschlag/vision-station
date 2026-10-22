"""Brightness tool: the gray level of a region (FR-PLT-9, tier 1).

It answers whether a region is lit as it should be: a lamp that is on, a label that is clear, a window that is not
blown out. Gray levels go from 0 (black) to 255 (white). What fails:

- the **mean** below `min_mean` or above `max_mean`;
- the **standard deviation** (how much the level varies in the region) above `max_std`: a surface that should be
  even and has a stain or a gradient;
- a **share above or below a level**, the form that prohibits: `max_above` is the most pixels that may be brighter
  than `level` (no glare), `max_below` the most that may be darker (no black hole).

Fields for `reason_fail`: {mean}, {std}, {min}, {max} (gray levels), {above}, {below} (the fractions beyond `level`,
format them with `:.0%`), the limits {min_mean}, {max_mean}, {max_std}, {max_above}, {max_below}, and {level}.
"""

from typing import Annotated, Self

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

from vision_station.algorithms.levels import level_stats, share_beyond
from vision_station.core.i18n import tr
from vision_station.core.jobfiles import JobFiles
from vision_station.core.results import Criterion, Unit
from vision_station.core.schema_labels import labels, meta
from vision_station.tools.base import CriterionSpec, ToolError, ToolResult, ToolType, judged, maximum, minimum, register

Share = Annotated[float, Field(ge=0, le=1)]
Gray = Annotated[float, Field(ge=0, le=255)]
TOP = 255.0  # the largest gray level


class BrightnessParams(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra=labels(
        "Mede o brilho (nível de cinza) de uma região.",
        meta={
            "min_mean": meta(1, "criteria", unit="score", tunable=True),
            "max_mean": meta(1, "criteria", unit="score", tunable=True),
            "max_std": meta(2, "criteria", unit="score", tunable=True),
            "level": meta(2, "measure", unit="score"),
            "max_above": meta(2, "criteria", unit="fraction", tunable=True),
            "max_below": meta(2, "criteria", unit="fraction", tunable=True),
        },
        min_mean=("Brilho médio mínimo", "0 (preto) a 255 (branco)"),
        max_mean=("Brilho médio máximo", "0 (preto) a 255 (branco)"),
        max_std=("Variação máxima", "Desvio padrão do brilho: baixo é uniforme, alto tem mancha ou degradê"),
        level=("Nível de comparação", "0 a 255: a referência de 'acima do nível' e 'abaixo do nível'"),
        max_above=("Máximo acima do nível", "0 a 1: parte da região mais clara que o nível (ex.: sem reflexo)"),
        max_below=("Máximo abaixo do nível", "0 a 1: parte da região mais escura que o nível (ex.: sem buraco preto)"),
    ))

    min_mean: Gray | None = None
    max_mean: Gray | None = None
    max_std: Gray | None = None
    level: Annotated[int, Field(ge=0, le=255)] = 128
    max_above: Share | None = None
    max_below: Share | None = None

    @model_validator(mode="after")
    def _criteria(self) -> Self:
        if all(v is None for v in (self.min_mean, self.max_mean, self.max_std, self.max_above, self.max_below)):
            raise ValueError("give at least one of min_mean, max_mean, max_std, max_above, max_below")
        if self.min_mean is not None and self.max_mean is not None and self.min_mean > self.max_mean:
            raise ValueError("min_mean must not be above max_mean")
        return self


def run(region: np.ndarray, params: BrightnessParams, files: JobFiles) -> ToolResult:
    if region.size == 0:
        raise ToolError("the region is empty")
    stats = level_stats(region)
    above, below = share_beyond(region, params.level)
    values: dict = {**stats, "above": above, "below": below, "level": params.level, "min_mean": params.min_mean, "max_mean": params.max_mean,
                    "max_std": params.max_std, "max_above": params.max_above, "max_below": params.max_below}
    criteria: list[Criterion] = []
    if params.min_mean is not None:
        criteria.append(minimum("min_mean", "mean", stats["mean"], params.min_mean))
    if params.max_mean is not None:
        criteria.append(maximum("max_mean", "mean", stats["mean"], params.max_mean, TOP))
    if params.max_std is not None:
        criteria.append(maximum("max_std", "std", stats["std"], params.max_std, TOP))
    if params.max_above is not None:
        criteria.append(maximum("max_above", "above", above, params.max_above))
    if params.max_below is not None:
        criteria.append(maximum("max_below", "below", below, params.max_below))
    units: dict[str, Unit] = {"mean": "score", "std": "score", "min": "score", "max": "score", "above": "fraction", "below": "fraction"}
    return judged(criteria, values=values, details=dict(stats), units=units)  # no marks: it measures the whole region, whose outline is its drawing


BRIGHTNESS = register(ToolType(
    name="brightness", version=1, params=BrightnessParams, run=run,
    criteria=(
        CriterionSpec("mean", tr("Brilho médio"), "score", "min_mean", "max_mean", (0.0, TOP)),
        CriterionSpec("std", tr("Variação do brilho"), "score", None, "max_std", (0.0, TOP), level=2),
        CriterionSpec("above", tr("Parte acima do nível"), "fraction", None, "max_above", (0.0, 1.0), level=2),
        CriterionSpec("below", tr("Parte abaixo do nível"), "fraction", None, "max_below", (0.0, 1.0), level=2),
    ),
))
