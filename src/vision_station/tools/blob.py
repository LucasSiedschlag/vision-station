"""Blob tool: counts and measures the parts of a region that stand out (FR-PLT-9, tier 1).

A blob is a connected part of the region that is of a colour, or darker or lighter than the rest (`mode`, as in the `blob`
locator), after small specks are cleaned. Only the ones whose area is inside the filter count. Use it to know how many
there are (screws, holes, drops of glue), how much they cover, or that none is too large (a stain, a burr).

What fails, each when it is given:

- the **count** below `min_count` or above `max_count`;
- the **total area** of the blobs that count below `min_area` or above `max_area`;
- the **largest blob** above `max_largest`: the form that prohibits (no part larger than this).

The filter and the limits are in pixels, or in square millimetres (`..._mm2`) in a calibrated job (FR-INS-15): a job that
uses millimetres with no calibration is refused. A calibrated job reports the areas in both.

Fields for `reason_fail`: {count} (the blobs that count), {area}, {largest} (areas in pixels), {area_mm2} and
{largest_mm2} (square millimetres, only in a calibrated job), the limits {min_count}, {max_count}, {min_area}, {max_area},
{max_largest}, {min_area_mm2}, {max_area_mm2}, {max_largest_mm2}, and the filter {filter_min}, {filter_max},
{filter_min_mm2}, {filter_max_mm2}.
"""

from typing import Annotated, Literal, Self

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

from vision_station.algorithms.blobs import binary_mask, clean_mask, components
from vision_station.algorithms.color import ColorRange
from vision_station.algorithms.outlines import mask_outlines
from vision_station.core.i18n import tr
from vision_station.core.jobfiles import JobFiles
from vision_station.core.results import MAX_MARKS, Criterion, Mark, Unit
from vision_station.core.schema_labels import labels, meta
from vision_station.tools.base import CriterionSpec, ToolError, ToolResult, ToolType, count_at_most, judged, maximum, minimum, register

AUTO_MIN_CONTRAST = 30  # gray levels: with the automatic threshold, a region flatter than this has nothing that stands out

Area = Annotated[float, Field(ge=0, allow_inf_nan=False)]


class BlobToolParams(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra=labels(
        "Conta e mede as manchas (partes ligadas) de uma região que se destacam por cor ou por brilho.",
        meta={
            "mode": meta(1, "measure"),
            "color": meta(1, "measure"),
            "threshold": meta(2, "measure", widget="gray-threshold"),
            "clean_px": meta(2, "measure", unit="px"),
            "filter_min": meta(2, "measure", unit="px2"),
            "filter_max": meta(2, "measure", unit="px2"),
            "filter_min_mm2": meta(2, "measure", unit="mm2"),
            "filter_max_mm2": meta(2, "measure", unit="mm2"),
            "min_count": meta(1, "criteria", unit="count", tunable=True),
            "max_count": meta(1, "criteria", unit="count", tunable=True),
            "min_area": meta(1, "criteria", unit="px2", tunable=True),
            "max_area": meta(1, "criteria", unit="px2", tunable=True),
            "max_largest": meta(1, "criteria", unit="px2", tunable=True),
            "min_area_mm2": meta(2, "criteria", unit="mm2", tunable=True),
            "max_area_mm2": meta(2, "criteria", unit="mm2", tunable=True),
            "max_largest_mm2": meta(2, "criteria", unit="mm2", tunable=True),
        },
        mode=("As manchas são", "", {"color": "de uma cor", "dark": "mais escuras que o fundo", "light": "mais claras que o fundo"}),
        color=("Cor das manchas", ""),
        threshold=("Limiar de cinza", "0 a 255. Vazio: automático"),
        clean_px=("Limpeza (px)", "Fecha furos pequenos e remove pontinhos; 0: mede a máscara como ela é"),
        filter_min=("Menor mancha que conta (px²)", "Manchas menores que isso são ignoradas"),
        filter_max=("Maior mancha que conta (px²)", "Vazio: sem limite; manchas maiores que isso são ignoradas"),
        filter_min_mm2=("Menor mancha que conta (mm²)", "Precisa da calibração do job"),
        filter_max_mm2=("Maior mancha que conta (mm²)", "Precisa da calibração do job"),
        min_count=("Mínimo de manchas", "Quantas precisam existir"),
        max_count=("Máximo de manchas", "Mais que isso reprova"),
        min_area=("Área total mínima (px²)", "Soma das manchas que contam"),
        max_area=("Área total máxima (px²)", "Soma das manchas que contam"),
        max_largest=("Maior mancha, no máximo (px²)", "Uma mancha maior que isso reprova (ex.: uma rebarba)"),
        min_area_mm2=("Área total mínima (mm²)", "Precisa da calibração do job"),
        max_area_mm2=("Área total máxima (mm²)", "Precisa da calibração do job"),
        max_largest_mm2=("Maior mancha, no máximo (mm²)", "Precisa da calibração do job"),
    ))

    mode: Literal["color", "dark", "light"]
    color: ColorRange | None = None
    threshold: Annotated[int, Field(ge=0, le=255)] | None = None  # for 'dark' and 'light'; None: automatic (Otsu)
    clean_px: Annotated[int, Field(ge=0, le=50)] = 0  # a measure is not biased by cleaning; the area filter drops specks
    filter_min: Area = 20  # px²: smaller parts are noise
    filter_max: Area | None = None
    filter_min_mm2: Area | None = None
    filter_max_mm2: Area | None = None
    min_count: Annotated[int, Field(ge=0)] | None = None
    max_count: Annotated[int, Field(ge=0)] | None = None
    min_area: Area | None = None
    max_area: Area | None = None
    max_largest: Area | None = None
    min_area_mm2: Area | None = None
    max_area_mm2: Area | None = None
    max_largest_mm2: Area | None = None

    @model_validator(mode="after")
    def _valid(self) -> Self:
        if self.mode == "color" and self.color is None:
            raise ValueError("mode 'color' needs color")
        limits = (self.min_count, self.max_count, self.min_area, self.max_area, self.max_largest, self.min_area_mm2, self.max_area_mm2, self.max_largest_mm2)
        if all(v is None for v in limits):
            raise ValueError("give at least one limit: min_count, max_count, min_area, max_area, max_largest or the ones in mm2")
        for low, high in ((self.min_count, self.max_count), (self.min_area, self.max_area), (self.min_area_mm2, self.max_area_mm2), (self.filter_min, self.filter_max), (self.filter_min_mm2, self.filter_max_mm2)):
            if low is not None and high is not None and low > high:
                raise ValueError("a minimum must not be above its maximum")
        return self


def run(region: np.ndarray, params: BlobToolParams, files: JobFiles) -> ToolResult:
    if region.size == 0:
        raise ToolError("the region is empty")
    mask = clean_mask(binary_mask(region, params.mode, params.color, params.threshold, AUTO_MIN_CONTRAST), params.clean_px)
    _, labels_, stats = components(mask)
    areas = stats[1:, 4].astype(float)  # px, the pixels of the frame (the cut keeps them)
    low, high = params.filter_min, params.filter_max
    needs_mm = any(v is not None for v in (params.filter_min_mm2, params.filter_max_mm2, params.min_area_mm2, params.max_area_mm2, params.max_largest_mm2))
    # a limit in mm² needs the scale (the tool cannot run without it); a calibrated job reports mm² anyway
    scale = files.scale() if needs_mm or files.calibrated else None
    px_to_mm2 = scale.x * scale.y if scale is not None else None
    keep = (areas >= low) & ((areas <= high) if high is not None else True)
    if px_to_mm2 is not None:
        if params.filter_min_mm2 is not None:
            keep &= areas * px_to_mm2 >= params.filter_min_mm2
        if params.filter_max_mm2 is not None:
            keep &= areas * px_to_mm2 <= params.filter_max_mm2
    kept = areas[keep]
    count = int(kept.size)
    area = float(kept.sum())
    largest = float(kept.max()) if count else 0.0
    values: dict = {"count": count, "area": area, "largest": largest, "filter_min": params.filter_min, "filter_max": params.filter_max,
                    "filter_min_mm2": params.filter_min_mm2, "filter_max_mm2": params.filter_max_mm2, "min_count": params.min_count, "max_count": params.max_count,
                    "min_area": params.min_area, "max_area": params.max_area, "max_largest": params.max_largest, "min_area_mm2": params.min_area_mm2,
                    "max_area_mm2": params.max_area_mm2, "max_largest_mm2": params.max_largest_mm2}
    units: dict[str, Unit] = {"count": "count", "area": "px2", "largest": "px2"}
    top = float(region.shape[0] * region.shape[1])  # no area is larger than the region
    criteria: list[Criterion] = []
    if params.min_count is not None:
        criteria.append(minimum("min_count", "count", count, params.min_count))
    if params.max_count is not None:
        criteria.append(count_at_most("max_count", "count", count, params.max_count))
    if params.min_area is not None:
        criteria.append(minimum("min_area", "area", area, params.min_area))
    if params.max_area is not None:
        criteria.append(maximum("max_area", "area", area, params.max_area, top))
    if params.max_largest is not None:
        criteria.append(maximum("max_largest", "largest", largest, params.max_largest, top))
    if px_to_mm2 is not None:
        area_mm2, largest_mm2 = area * px_to_mm2, largest * px_to_mm2
        values.update(area_mm2=area_mm2, largest_mm2=largest_mm2)
        units.update(area_mm2="mm2", largest_mm2="mm2")
        if params.min_area_mm2 is not None:
            criteria.append(minimum("min_area_mm2", "area_mm2", area_mm2, params.min_area_mm2))
        if params.max_area_mm2 is not None:
            criteria.append(maximum("max_area_mm2", "area_mm2", area_mm2, params.max_area_mm2, top * px_to_mm2))
        if params.max_largest_mm2 is not None:
            criteria.append(maximum("max_largest_mm2", "largest_mm2", largest_mm2, params.max_largest_mm2, top * px_to_mm2))
    # the outline of each blob that counts, the largest first; too much of what is limited from above is the defect
    ids = np.flatnonzero(keep) + 1
    shown = np.isin(labels_, ids[np.argsort(-areas[keep], kind="stable")[:MAX_MARKS]])
    role = "defect" if any(c.code.startswith("max_") and not c.passed for c in criteria) else "found"
    marks = tuple(Mark("poly", role, points) for points in mask_outlines(shown, most=MAX_MARKS))
    return judged(criteria, values=values, details={"count": count, "area": area, "largest": largest, "all": int(areas.size)}, units=units, marks=marks)


BLOB = register(ToolType(
    name="blob", version=1, params=BlobToolParams, run=run,
    criteria=(
        CriterionSpec("count", tr("Manchas"), "count", "min_count", "max_count"),
        CriterionSpec("area", tr("Área das manchas"), "px2", "min_area", "max_area"),
        CriterionSpec("largest", tr("Maior mancha"), "px2", None, "max_largest"),
        CriterionSpec("area_mm2", tr("Área das manchas (mm²)"), "mm2", "min_area_mm2", "max_area_mm2", level=2),
        CriterionSpec("largest_mm2", tr("Maior mancha (mm²)"), "mm2", None, "max_largest_mm2", level=2),
    ),
))
