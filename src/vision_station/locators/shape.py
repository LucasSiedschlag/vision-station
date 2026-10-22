"""Shape locator: finds a taught pattern by the direction of its edges, turned and scaled (FR-INS-11, TD-25).

The template is an image inside the job (e.g. `locator/shape.png`), cut from the reference image. Unlike the `template`
locator it follows the object when it is turned (`angles`) or larger or smaller (`scales`), does not care about the brightness
(only the direction of the edges counts), and tolerates a part hidden: the score falls by the share hidden. The anchor is a pose
(architecture §14): where the template matched, its angle and its scale, with the size of the template. With `polarity` `ignore` a
pattern with its light and dark reversed matches too. The whole pattern must be inside the search area to be found.
"""

from typing import Annotated, Literal, Self

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

from vision_station.algorithms.shapematch import find_shapes, model_from_png
from vision_station.core.jobfiles import JobFiles
from vision_station.core.schema_labels import labels, meta
from vision_station.geometry.pose import Fixture
from vision_station.locators.base import LocatorError, LocatorType, register

Fraction = Annotated[float, Field(ge=0, le=1)]


class ShapeParams(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra=labels(
        "Acha o objeto pelo contorno ensinado, girado e em outro tamanho; a âncora tem a posição, o ângulo e o tamanho dele.",
        meta={
            "template": meta(1, "measure", widget="template"),
            "search": meta(2, "measure", widget="region"),
            "angles": meta(1, "measure"),
            "scales": meta(2, "measure"),
            "min_score": meta(1, "criteria", unit="score"),
            "polarity": meta(3, "measure"),
        },
        template=("Gabarito", "Imagem do objeto dentro do job, recortada da imagem de referência"),
        search=("Área de busca (x0, y0, x1, y1)", "Frações da imagem; o objeto inteiro precisa estar aqui"),
        angles=("Ângulos (de, até)", "Graus; quanto o objeto pode estar girado em relação ao ensinado. Quanto menor a faixa, mais rápido"),
        scales=("Tamanhos (de, até)", "1 é o tamanho ensinado; 0,9 a 1,1 aceita 10% menor ou maior"),
        min_score=("Semelhança mínima", "0 a 1; abaixo disso o objeto não foi encontrado"),
        polarity=("Claro e escuro", "Se o objeto pode aparecer com o claro e o escuro trocados", {"same": "como ensinado", "ignore": "aceitar trocados"}),
    ))

    template: Annotated[str, Field(min_length=1)]  # image inside the job
    search: tuple[Fraction, Fraction, Fraction, Fraction] = (0.0, 0.0, 1.0, 1.0)
    angles: tuple[Annotated[float, Field(ge=-180, le=180)], Annotated[float, Field(ge=-180, le=180)]] = (-20.0, 20.0)
    scales: tuple[Annotated[float, Field(gt=0, le=4)], Annotated[float, Field(gt=0, le=4)]] = (0.9, 1.1)
    min_score: Annotated[float, Field(gt=0, le=1)] = 0.7
    polarity: Literal["same", "ignore"] = "same"

    @model_validator(mode="after")
    def _valid(self) -> Self:
        x0, y0, x1, y1 = self.search
        if not (x0 < x1 and y0 < y1):
            raise ValueError("search must be [x0, y0, x1, y1] with x0 < x1 and y0 < y1")
        if self.angles[0] > self.angles[1] or self.scales[0] > self.scales[1]:
            raise ValueError("angles and scales are ranges, low to high")
        return self


def locate(frame: np.ndarray, params: ShapeParams, files: JobFiles) -> Fixture | None:
    try:
        model = model_from_png(files.bytes(params.template))
    except ValueError as exc:
        raise LocatorError(f"template {params.template}: {exc}") from exc
    if frame.size == 0:
        return None
    height, width = frame.shape[:2]
    sx0, sy0, sx1, sy1 = (round(v * n) for v, n in zip(params.search, (width, height, width, height)))
    area = frame[sy0:sy1, sx0:sx1]
    try:
        found = find_shapes(area, model, angles=params.angles, scales=params.scales, min_score=params.min_score, polarity=params.polarity)
    except ValueError as exc:
        raise LocatorError(str(exc)) from exc
    if not found:
        return None
    match = found[0]
    tw, th = model.size
    cx, cy = sx0 + match.x + 0.5, sy0 + match.y + 0.5  # from the index of a pixel to the boundary coordinates fractions are of
    rect = ((cx - tw / 2) / width, (cy - th / 2) / height, (cx + tw / 2) / width, (cy + th / 2) / height)
    return Fixture(rect=rect, angle=match.angle, scale=match.scale, score=float(match.score))


SHAPE = register(LocatorType(name="shape", version=1, params=ShapeParams, locate=locate, needs=lambda p: [p.template]))
