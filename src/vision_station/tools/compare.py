"""Compare tool: finds where a part differs from what good parts look like (FR-PLT-9, tier 1; TD-25).

The tool is taught with pictures of good parts (`teach` in `algorithms/variation.py`, or `scripts/teach_compare.py`): the mean
and the standard deviation of every pixel of the region, kept in a file of the job (`models/<name>.var`). Each part is moved to
the model (registered, up to `max_shift_px`), its light is divided by one gain (a part 15 % darker is the same part; 40 % darker is
not), and a pixel is a defect when it differs from the mean by more than `max(abs_threshold, k * sigma + edge_px * the change to
its neighbours)`: the floor, what the good parts varied, and what a pixel of misregistration changes on an edge. The defects are
the connected parts of those pixels, cleaned (`clean_px`) and with the ones smaller than `filter_min` dropped. Use at least 15
pictures: with fewer the floor and the edge term hold the tolerance, not what the good parts showed.

What fails, each when it is given: more defects than `max_count`, a total area above `max_area`, the largest defect above
`max_largest`; in pixels, or in square millimetres (`..._mm2`) in a calibrated job (FR-INS-15). The region is the one of the
taught size (a fixture of another scale is resized to it, up to a quarter).

Fields for `reason_fail`: {count} (the defects that count), {area} and {largest} (the total and the largest, in pixels of the region),
{area_mm2} and {largest_mm2} (square millimetres, only in a calibrated job), {gain} (the gain of the light, 1 is as taught), the
limits {max_count}, {max_area}, {max_largest}, {max_area_mm2}, {max_largest_mm2} and the filter {filter_min}.
"""

from typing import Annotated, Self

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

from vision_station.algorithms import variation
from vision_station.algorithms.blobs import clean_mask, components
from vision_station.algorithms.outlines import mask_outlines
from vision_station.core.i18n import tr
from vision_station.core.jobfiles import JobFiles
from vision_station.core.results import MAX_MARKS, Criterion, Mark, Unit
from vision_station.core.schema_labels import labels, meta
from vision_station.tools.base import CriterionSpec, ToolError, ToolResult, ToolType, count_at_most, judged, maximum, register

Area = Annotated[float, Field(ge=0, allow_inf_nan=False)]


class CompareParams(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra=labels(
        "Acha onde a peça é diferente do que as peças boas ensinadas mostraram.",
        meta={
            "model": meta(1, "measure"),
            "abs_threshold": meta(2, "measure", unit="score"),
            "k": meta(2, "measure"),
            "edge_px": meta(3, "measure", unit="px"),
            "max_shift_px": meta(3, "measure", unit="px"),
            "normalize": meta(3, "measure"),
            "clean_px": meta(2, "measure", unit="px"),
            "filter_min": meta(2, "measure", unit="px2"),
            "max_count": meta(1, "criteria", unit="count", tunable=True),
            "max_area": meta(1, "criteria", unit="px2", tunable=True),
            "max_largest": meta(1, "criteria", unit="px2", tunable=True),
            "max_area_mm2": meta(2, "criteria", unit="mm2", tunable=True),
            "max_largest_mm2": meta(2, "criteria", unit="mm2", tunable=True),
        },
        model=("Modelo ensinado", "Arquivo .var dentro do job, ensinado com peças boas"),
        abs_threshold=("Diferença mínima", "Níveis de cinza; abaixo disso nunca é defeito"),
        k=("Quantos desvios", "Quantas vezes o desvio das peças boas um pixel pode variar"),
        edge_px=("Folga nas bordas (px)", "Quanto uma borda pode estar fora do lugar sem ser defeito"),
        max_shift_px=("Deslocamento máximo (px)", "Quanto a peça é movida para se alinhar ao modelo"),
        normalize=("Corrigir a luz", "Divide a imagem por um ganho, para uma luz 15% mais fraca ou forte não ser defeito"),
        clean_px=("Limpeza (px)", "Remove pontinhos de defeito; 0: mede a máscara como ela é"),
        filter_min=("Menor defeito que conta (px²)", "Defeitos menores que isso são ignorados"),
        max_count=("Máximo de defeitos", "Mais que isso reprova"),
        max_area=("Área total máxima (px²)", "Soma dos defeitos que contam; 0: nenhum pixel de defeito"),
        max_largest=("Maior defeito, no máximo (px²)", "Um defeito maior que isso reprova"),
        max_area_mm2=("Área total máxima (mm²)", "Precisa da calibração do job"),
        max_largest_mm2=("Maior defeito, no máximo (mm²)", "Precisa da calibração do job"),
    ))

    model: Annotated[str, Field(min_length=1)]  # file inside the job
    abs_threshold: Annotated[float, Field(ge=1, le=255)] = 15
    k: Annotated[float, Field(ge=0, le=10)] = 3
    edge_px: Annotated[float, Field(ge=0, le=5)] = 1.0
    max_shift_px: Annotated[float, Field(ge=0, le=30)] = 6
    normalize: bool = True
    clean_px: Annotated[int, Field(ge=0, le=20)] = 0
    filter_min: Area = 10
    max_count: Annotated[int, Field(ge=0)] | None = None
    max_area: Area | None = None
    max_largest: Area | None = None
    max_area_mm2: Area | None = None
    max_largest_mm2: Area | None = None

    @model_validator(mode="after")
    def _valid(self) -> Self:
        if all(v is None for v in (self.max_count, self.max_area, self.max_largest, self.max_area_mm2, self.max_largest_mm2)):
            raise ValueError("give at least one limit: max_count, max_area, max_largest or the ones in mm2")
        return self


def run(region: np.ndarray, params: CompareParams, files: JobFiles) -> ToolResult:
    try:
        model = variation.load(files.bytes(params.model))
    except ValueError as exc:
        raise ToolError(f"model {params.model}: {exc}") from exc
    if region.size == 0:
        raise ToolError("the region is empty")
    try:
        compared = variation.compare(region, model, abs_threshold=params.abs_threshold, k=params.k, edge_px=params.edge_px,
                                     max_shift=params.max_shift_px, normalize=params.normalize)
    except ValueError as exc:
        raise ToolError(str(exc)) from exc
    sx, sy = compared.scale
    mask = clean_mask(compared.mask, params.clean_px)
    _, labels_, stats = components(mask)
    areas = stats[1:, 4].astype(float) * (sx * sy)  # pixels of the region, whatever the size the comparison was made in
    keep = areas >= params.filter_min
    kept = areas[keep]
    count, area = int(kept.size), float(kept.sum())
    largest = float(kept.max()) if count else 0.0
    needs_mm = params.max_area_mm2 is not None or params.max_largest_mm2 is not None
    scale = files.scale() if needs_mm or files.calibrated else None  # a limit in mm² needs the scale; a calibrated job reports it anyway
    to_mm2 = scale.x * scale.y if scale is not None else None
    values: dict = {"count": count, "area": area, "largest": largest, "gain": compared.gain[0], "filter_min": params.filter_min,
                    "max_count": params.max_count, "max_area": params.max_area, "max_largest": params.max_largest,
                    "max_area_mm2": params.max_area_mm2, "max_largest_mm2": params.max_largest_mm2}
    units: dict[str, Unit] = {"count": "count", "area": "px2", "largest": "px2", "gain": "score"}
    top = float(region.shape[0] * region.shape[1])  # no area is larger than the region
    criteria: list[Criterion] = []
    if params.max_count is not None:
        criteria.append(count_at_most("max_count", "count", count, params.max_count))
    if params.max_area is not None:
        criteria.append(maximum("max_area", "area", area, params.max_area, top))
    if params.max_largest is not None:
        criteria.append(maximum("max_largest", "largest", largest, params.max_largest, top))
    if to_mm2 is not None:
        values.update(area_mm2=area * to_mm2, largest_mm2=largest * to_mm2)
        units.update(area_mm2="mm2", largest_mm2="mm2")
        if params.max_area_mm2 is not None:
            criteria.append(maximum("max_area_mm2", "area_mm2", area * to_mm2, params.max_area_mm2, top * to_mm2))
        if params.max_largest_mm2 is not None:
            criteria.append(maximum("max_largest_mm2", "largest_mm2", largest * to_mm2, params.max_largest_mm2, top * to_mm2))
    # the outline of each defect that counts, the largest first, back in the pixels of the region
    ids = np.flatnonzero(keep) + 1
    shown = np.isin(labels_, ids[np.argsort(-areas[keep], kind="stable")[:MAX_MARKS]])
    dx, dy = compared.shift
    height, width = region.shape[:2]
    role = "defect" if any(not c.passed for c in criteria) else "found"  # the defects of a part that fails, else the ones allowed
    marks = tuple(
        Mark("poly", role, tuple((float(np.clip((x - dx) * sx, 0, width)), float(np.clip((y - dy) * sy, 0, height))) for x, y in points))
        for points in (mask_outlines(shown, most=MAX_MARKS) if count else ())  # a good part, the common case, has nothing to outline
    )
    return judged(criteria, values=values, details={"count": count, "area": area, "largest": largest, "gain": list(compared.gain), "shift": list(compared.shift)},
                  units=units, marks=marks)


COMPARE = register(ToolType(
    name="compare", version=1, params=CompareParams, run=run, needs=lambda p: [p.model],
    criteria=(
        CriterionSpec("count", tr("Defeitos"), "count", None, "max_count"),
        CriterionSpec("area", tr("Área dos defeitos"), "px2", None, "max_area"),
        CriterionSpec("largest", tr("Maior defeito"), "px2", None, "max_largest"),
        CriterionSpec("area_mm2", tr("Área dos defeitos (mm²)"), "mm2", None, "max_area_mm2", level=2),
        CriterionSpec("largest_mm2", tr("Maior defeito (mm²)"), "mm2", None, "max_largest_mm2", level=2),
    ),
))
