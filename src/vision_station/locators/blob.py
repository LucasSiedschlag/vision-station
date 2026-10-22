"""Blob locator: the object is the largest region of a color, or darker or lighter than the background.

For objects that stand out from what is around them: a box on a light bench, a colored part, a dark
label. The region is the largest one whose area is between `min_area` and `max_area` (fractions of the search area).

- **v1** gives the upright rectangle around it. Its score is how much of that rectangle the region fills, so a
  square part gives about 1 and a rotated one less; the score is reported, not used to reject.
- **v2** gives a **pose** (architecture §14, FR-INS-11): the centre and the angle of the smallest rectangle around the
  region (`cv2.minAreaRect`), and the scale when the size the part has when it is placed as taught is given
  (`taught_size`). The score is how much of that turned rectangle the region fills. A rectangle looks the same turned by
  180°, and a square by 90°: with `taught_size` the angle is the one that puts the long side where it was taught, in
  (-90°, 90°]; without it, the angle is the smallest turn, in [-45°, 45°).
"""

import math

from typing import Annotated, Literal, Self

import cv2
import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

from vision_station.algorithms.blobs import binary_mask, clean_mask, components
from vision_station.algorithms.color import ColorRange
from vision_station.core.jobfiles import JobFiles
from vision_station.core.schema_labels import labels, meta
from vision_station.geometry.pose import Fixture
from vision_station.locators.base import LocatorType, register

Fraction = Annotated[float, Field(ge=0, le=1)]


class BlobParams(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra=labels(
        "O objeto é a maior região de uma cor, ou mais escura ou mais clara que o fundo.",
        meta={
            "mode": meta(1, "measure"),
            "color": meta(1, "measure"),
            "threshold": meta(1, "measure", widget="gray-threshold"),
            "search": meta(2, "measure", widget="region"),
            "min_area": meta(1, "criteria", unit="fraction"),
            "max_area": meta(1, "criteria", unit="fraction"),
            "clean_px": meta(2, "measure", unit="px"),
            "work_width": meta(3, "measure", unit="px"),
        },
        mode=("O objeto é", "", {"color": "de uma cor", "dark": "mais escuro que o fundo", "light": "mais claro que o fundo"}),
        color=("Cor do objeto", ""),
        threshold=("Limiar de cinza", "0 a 255. Vazio: automático"),
        search=("Área de busca (x0, y0, x1, y1)", "Frações da imagem"),
        min_area=("Área mínima", "Fração da área de busca"),
        max_area=("Área máxima", "Fração da área de busca"),
        clean_px=("Limpeza (px)", "Remove pontinhos e fecha furos pequenos"),
        work_width=("Largura de trabalho (px)", ""),
    ))

    mode: Literal["color", "dark", "light"]
    color: ColorRange | None = None  # for mode 'color'
    threshold: Annotated[int, Field(ge=0, le=255)] | None = None  # gray level for 'dark'/'light'; None = automatic (Otsu)
    search: tuple[Fraction, Fraction, Fraction, Fraction] = (0.0, 0.0, 1.0, 1.0)
    min_area: Annotated[float, Field(gt=0, le=1)] = 0.02
    max_area: Annotated[float, Field(gt=0, le=1)] = 1.0
    clean_px: Annotated[int, Field(ge=0, le=50)] = 3  # removes specks and fills small holes, at work size
    work_width: Annotated[int, Field(ge=64, le=4096)] = 640

    @model_validator(mode="after")
    def _valid(self) -> Self:
        x0, y0, x1, y1 = self.search
        if not (x0 < x1 and y0 < y1):
            raise ValueError("search must be [x0, y0, x1, y1] with x0 < x1 and y0 < y1")
        if self.mode == "color" and self.color is None:
            raise ValueError("mode 'color' needs color")
        if self.min_area > self.max_area:
            raise ValueError("min_area must not be above max_area")
        return self


class _Found:
    """The largest region in range: its box and area at work size, and what maps work size back to the frame."""

    def __init__(self, mask: np.ndarray, label: int, stats: np.ndarray, sx0: int, sy0: int, scale: float, size: tuple[int, int]):
        self.mask, self.label, self.stats, self.sx0, self.sy0, self.scale, self.size = mask, label, stats, sx0, sy0, scale, size


def _search(frame: np.ndarray, params: BlobParams) -> "_Found | None":
    height, width = frame.shape[:2]
    sx0, sy0, sx1, sy1 = (round(v * n) for v, n in zip(params.search, (width, height, width, height)))
    area = frame[sy0:sy1, sx0:sx1]
    if area.size == 0:
        return None
    scale = min(1.0, params.work_width / width)
    if scale < 1.0:
        area = cv2.resize(area, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    mask = clean_mask(binary_mask(area, params.mode, params.color, params.threshold), params.clean_px)
    count, labels_, stats = components(mask)
    total = mask.shape[0] * mask.shape[1]
    best = None
    for i in range(1, count):
        if params.min_area * total <= stats[i][4] <= params.max_area * total and (best is None or stats[i][4] > stats[best][4]):
            best = i
    if best is None:
        return None
    return _Found(labels_ == best, best, stats[best], sx0, sy0, scale, (width, height))


def locate(frame: np.ndarray, params: BlobParams, files: JobFiles) -> Fixture | None:
    found = _search(frame, params)
    if found is None:
        return None
    width, height = found.size
    x, y, w, h, a = found.stats
    rect = ((found.sx0 + x / found.scale) / width, (found.sy0 + y / found.scale) / height, min(1.0, (found.sx0 + (x + w) / found.scale) / width), min(1.0, (found.sy0 + (y + h) / found.scale) / height))
    return Fixture(rect=rect, score=float(a / (w * h)))


class BlobParamsV2(BlobParams):
    model_config = ConfigDict(extra="forbid", json_schema_extra=labels(
        "O objeto é a maior região de uma cor, ou mais escura ou mais clara que o fundo; a âncora tem a posição, o ângulo e o tamanho dele.",
        meta={
            "mode": meta(1, "measure"),
            "color": meta(1, "measure"),
            "threshold": meta(1, "measure", widget="gray-threshold"),
            "search": meta(2, "measure", widget="region"),
            "min_area": meta(1, "criteria", unit="fraction"),
            "max_area": meta(1, "criteria", unit="fraction"),
            "clean_px": meta(2, "measure", unit="px"),
            "work_width": meta(3, "measure", unit="px"),
            "taught_size": meta(2, "measure", unit="px"),
        },
        mode=("O objeto é", "", {"color": "de uma cor", "dark": "mais escuro que o fundo", "light": "mais claro que o fundo"}),
        color=("Cor do objeto", ""),
        threshold=("Limiar de cinza", "0 a 255. Vazio: automático"),
        search=("Área de busca (x0, y0, x1, y1)", "Frações da imagem"),
        min_area=("Área mínima", "Fração da área de busca"),
        max_area=("Área máxima", "Fração da área de busca"),
        clean_px=("Limpeza (px)", "Remove pontinhos e fecha furos pequenos"),
        work_width=("Largura de trabalho (px)", ""),
        taught_size=("Tamanho ensinado (largura, altura em px)", "O tamanho do objeto na imagem de referência. Com ele o programa sabe qual lado é o comprido e mede a escala; vazio: só o ângulo menor"),
    ))

    taught_size: tuple[Annotated[float, Field(gt=0)], Annotated[float, Field(gt=0)]] | None = None


def _normal(angle: float, square: bool) -> float:
    """An angle of a rectangle in its natural range: (-90, 90] for a long thing, [-45, 45) for a square one."""
    if square:
        return (angle + 45.0) % 90.0 - 45.0
    angle = (angle + 90.0) % 180.0 - 90.0
    return 90.0 if angle == -90.0 else angle


def locate_pose(frame: np.ndarray, params: BlobParamsV2, files: JobFiles) -> Fixture | None:
    found = _search(frame, params)
    if found is None:
        return None
    width, height = found.size
    points = cv2.findNonZero(found.mask.astype(np.uint8))
    (mx, my), (rw, rh), cv_angle = cv2.minAreaRect(points)
    if rw < 1 or rh < 1:
        return None
    # OpenCV's angle turns the `rw` side clockwise on the screen; ours is counter-clockwise
    angle = -float(cv_angle)
    cx = found.sx0 + mx / found.scale
    cy = found.sy0 + my / found.scale
    rw, rh = rw / found.scale, rh / found.scale
    score = float(found.stats[4] / (rw * rh * found.scale * found.scale))
    if params.taught_size is None:
        w, h, scale = rw, rh, 1.0
        angle = _normal(angle, square=False)
        if abs(angle) > 45.0:  # the smallest turn: swap the sides rather than turn more than 45°
            w, h = h, w
            angle = _normal(angle + 90.0, square=True)
    else:
        tw, th = params.taught_size
        # which side of the box is the taught width: the assignment whose proportions are the closest to the taught ones
        straight = abs(math.log(rw / tw)) + abs(math.log(rh / th))
        swapped = abs(math.log(rh / tw)) + abs(math.log(rw / th))
        if swapped < straight:
            rw, rh = rh, rw
            angle += 90.0
        square = abs(math.log(tw / th)) < 0.05
        angle = _normal(angle, square)
        w, h, scale = tw, th, math.sqrt((rw * rh) / (tw * th))
    rect = ((cx - w / 2) / width, (cy - h / 2) / height, (cx + w / 2) / width, (cy + h / 2) / height)
    return Fixture(rect=rect, angle=angle, scale=scale, score=min(1.0, score))


BLOB = register(LocatorType(name="blob", version=1, params=BlobParams, locate=locate))
BLOB_V2 = register(LocatorType(name="blob", version=2, params=BlobParamsV2, locate=locate_pose))
