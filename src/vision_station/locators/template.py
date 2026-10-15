"""Template locator: finds a taught picture of the object (or of a mark on it) in the frame.

The template is an image inside the job (e.g. `locator/template.png`), cut from the reference image, so it
has the frame's scale. Matching is normalized correlation on gray levels (OpenCV TM_CCOEFF_NORMED): it
tolerates changes of overall brightness and contrast and a shift anywhere in the search area, not a
rotation or a change of size. The anchor is where the template matched, with the template's size.
"""

from typing import Annotated, Self

import cv2
import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

from vision_station.jobfiles import JobFiles
from vision_station.schema_labels import labels
from vision_station.locators.base import Anchor, LocatorError, LocatorType, register

Fraction = Annotated[float, Field(ge=0, le=1)]


class TemplateParams(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra=labels(
        template=("Gabarito", "Imagem do objeto dentro do job, recortada da imagem de referência"),
        search=("Área de busca (x0, y0, x1, y1)", "Frações da imagem; o objeto é procurado só aqui"),
        min_score=("Semelhança mínima", "0 a 1; abaixo disso o objeto não foi encontrado"),
        work_width=("Largura de trabalho (px)", "A imagem é comparada nesta largura, para ser rápido"),
    ))

    template: Annotated[str, Field(min_length=1)]  # image inside the job
    search: tuple[Fraction, Fraction, Fraction, Fraction] = (0.0, 0.0, 1.0, 1.0)  # where to look, fractions of the frame
    min_score: Annotated[float, Field(gt=0, le=1)] = 0.6  # below this, the object is not found
    work_width: Annotated[int, Field(ge=64, le=4096)] = 640  # the frame is matched at this width, for speed

    @model_validator(mode="after")
    def _valid(self) -> Self:
        x0, y0, x1, y1 = self.search
        if not (x0 < x1 and y0 < y1):
            raise ValueError("search must be [x0, y0, x1, y1] with x0 < x1 and y0 < y1")
        return self


def _gray(image: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image


def locate(frame: np.ndarray, params: TemplateParams, files: JobFiles) -> Anchor | None:
    template = files.image(params.template, gray=True)
    if float(template.std()) < 1.0:
        raise LocatorError(f"template {params.template} is flat: nothing to match")
    height, width = frame.shape[:2]
    scale = min(1.0, params.work_width / width)
    sx0, sy0, sx1, sy1 = (round(v * n) for v, n in zip(params.search, (width, height, width, height)))
    area = _gray(frame[sy0:sy1, sx0:sx1])
    if scale < 1.0:
        area = cv2.resize(area, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        template = cv2.resize(template, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    th, tw = template.shape
    if th < 4 or tw < 4 or th > area.shape[0] or tw > area.shape[1]:
        return None  # the template does not fit in the search area
    result = np.nan_to_num(cv2.matchTemplate(area, template, cv2.TM_CCOEFF_NORMED), nan=-1.0)
    _, best, _, (mx, my) = cv2.minMaxLoc(result)
    if best < params.min_score:
        return None
    x0 = sx0 + mx / scale
    y0 = sy0 + my / scale
    rect = (x0 / width, y0 / height, min(1.0, (x0 + tw / scale) / width), min(1.0, (y0 + th / scale) / height))
    return Anchor(rect=rect, score=float(best))


TEMPLATE = register(LocatorType(name="template", version=1, params=TemplateParams, locate=locate, needs=lambda p: [p.template]))
