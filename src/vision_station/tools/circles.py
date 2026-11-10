"""Circles tool: counts the round parts of a region (rings, washers, caps, holes), tier 1.

Use it when what matters is **how many** round parts there are and the parts do not look the same to a template (a metal ring
catches the light differently at each angle), or their colour depends on the light. A circle is found by its edge: the region's
gray levels are equalised in small tiles, so the count means the same under a dimmer or a harsher light, and the circles of a
radius from `radius_min` to `radius_max` pixels that are round enough (`min_roundness`) are counted. Two circles never stand
closer than `min_distance` (default: twice `radius_min`), so the inner and the outer edge of one ring are one circle.

What fails, each when it is given:

- the **count** below `min_count` or above `max_count`.

The count is exact on clean, evenly lit parts and can be one or two off on a harder picture (glare, a part half in shadow, shapes
that look round, like a letter O). Where "one more is a defect", leave a margin in the limit and check it with real parts.

Fields for `reason_fail`: {count} (the circles found), {radius} (their mean radius in pixels, 0 with none), the limits
{min_count} and {max_count}.
"""

import math
from typing import Annotated, Self

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

from vision_station.algorithms.circles import Circle, find_circles
from vision_station.core.i18n import tr
from vision_station.core.jobfiles import JobFiles
from vision_station.core.results import MAX_MARKS, Criterion, Mark, Unit
from vision_station.core.schema_labels import labels, meta
from vision_station.tools.base import CriterionSpec, ToolError, ToolResult, ToolType, count_at_most, judged, minimum, register

OUTLINE_POINTS = 24  # the polygon that draws a circle; at most MAX_MARK_POINTS

Radius = Annotated[int, Field(ge=3, le=2000)]


class CirclesToolParams(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra=labels(
        "Conta as peças redondas de uma região (argolas, arruelas, tampas, furos) pela borda, sem depender da cor nem de um gabarito.",
        meta={
            "radius_min": meta(1, "measure", unit="px"),
            "radius_max": meta(1, "measure", unit="px"),
            "min_distance": meta(2, "measure", unit="px"),
            "min_roundness": meta(2, "measure", unit="score"),
            "min_count": meta(1, "criteria", unit="count", tunable=True),
            "max_count": meta(1, "criteria", unit="count", tunable=True),
        },
        radius_min=("Menor raio (px)", "Raio da menor peça, em pixels da imagem; com folga para o que varia"),
        radius_max=("Maior raio (px)", "Raio da maior peça, em pixels da imagem"),
        min_distance=("Distância mínima entre centros (px)", "Vazio: o dobro do menor raio. Duas bordas de uma mesma argola contam como uma peça só"),
        min_roundness=("Circularidade mínima", "0 a 1: quanto mais perto de 1, só círculos bem redondos; mais baixo acha mais, e acha o que não é círculo"),
        min_count=("Mínimo de peças", "Quantas precisam existir"),
        max_count=("Máximo de peças", "Mais que isso reprova"),
    ))

    radius_min: Radius
    radius_max: Radius
    min_distance: Annotated[float, Field(gt=0, allow_inf_nan=False)] | None = None
    min_roundness: Annotated[float, Field(gt=0, le=1)] = 0.7
    min_count: Annotated[int, Field(ge=0)] | None = None
    max_count: Annotated[int, Field(ge=0)] | None = None

    @model_validator(mode="after")
    def _valid(self) -> Self:
        if self.radius_max < self.radius_min:
            raise ValueError("radius_max must not be below radius_min")
        if self.min_count is None and self.max_count is None:
            raise ValueError("give at least one limit: min_count or max_count")
        if self.min_count is not None and self.max_count is not None and self.min_count > self.max_count:
            raise ValueError("a minimum must not be above its maximum")
        return self


def _outline(c: Circle, shape: tuple[int, ...]) -> tuple[tuple[float, float], ...]:
    """The circle as a closed polygon, kept inside the region (a circle at the edge is drawn as far as the picture goes)."""
    height, width = shape[:2]
    angles = np.linspace(0, 2 * math.pi, OUTLINE_POINTS, endpoint=False)
    return tuple((float(min(max(c.x + c.r * math.cos(a), 0.0), width)), float(min(max(c.y + c.r * math.sin(a), 0.0), height))) for a in angles)


def run(region: np.ndarray, params: CirclesToolParams, files: JobFiles) -> ToolResult:
    if region.size == 0:
        raise ToolError("the region is empty")
    distance = params.min_distance if params.min_distance is not None else 2.0 * params.radius_min
    circles = find_circles(region, params.radius_min, params.radius_max, distance, params.min_roundness)
    count = len(circles)
    radius = float(np.mean([c.r for c in circles])) if circles else 0.0
    values: dict = {"count": count, "radius": radius, "min_count": params.min_count, "max_count": params.max_count}
    units: dict[str, Unit] = {"count": "count", "radius": "px"}
    criteria: list[Criterion] = []
    if params.min_count is not None:
        criteria.append(minimum("min_count", "count", count, params.min_count))
    if params.max_count is not None:
        criteria.append(count_at_most("max_count", "count", count, params.max_count))
    role = "defect" if any(c.code == "max_count" and not c.passed for c in criteria) else "found"
    marks = tuple(Mark("poly", role, _outline(c, region.shape)) for c in circles[:MAX_MARKS])
    return judged(criteria, values=values, details={"count": count, "radius": radius}, units=units, marks=marks)


CIRCLES = register(ToolType(
    name="circles", version=1, params=CirclesToolParams, run=run,
    criteria=(CriterionSpec("count", tr("Peças redondas"), "count", "min_count", "max_count"),),
))
