"""Edges locator: the object is the corner of two edges (FR-INS-11, VIA-0075 E3).

For a part with a straight edge along two sides, like a sheet, a plate or a box seen from above: two calipers find the
**vertical** edge (it scans in x) and the **horizontal** one (it scans in y). Each caliper is a window cut in `bands` slices
across the edge; every slice gives one point (the strongest edge of the polarity), a line is fitted through the points (the ones
off the line are dropped), and the corner is where the two lines meet. The angle is the turn of the edges (the mean of the two).
The windows must lie along the edges, shorter than them, so that a turned part stays inside them.

The pose is the one of the part taught with `taught_rect` (its box) and `taught_corner` (where the corner was), both in fractions
of the frame: the box is put where the corner is, turned as the edges are. It is not found when an edge has no line (fewer than
half the slices find it) or the two edges are not at a right angle (more than 5° apart, an edge that is not straight or a corner
that is not square). Angles are counter-clockwise on the screen, like the pose.
"""

import math
from typing import Annotated, Literal, Self

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

from vision_station.algorithms.calipers import find_edges, profile
from vision_station.core.jobfiles import JobFiles
from vision_station.core.schema_labels import labels, meta
from vision_station.geometry.pose import Fixture
from vision_station.locators.base import LocatorType, register

Fraction = Annotated[float, Field(ge=0, le=1)]
Rect = tuple[Fraction, Fraction, Fraction, Fraction]
MAX_SKEW = 5.0  # degrees: the two edges are at a right angle to within this
MIN_WINDOW = 8  # pixels, across the edge: less is no window


class CaliperBox(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra=labels(
        "Uma janela sobre uma borda, dividida em faixas; cada faixa acha um ponto da borda.",
        meta={
            "rect": meta(1, "measure", widget="region"),
            "polarity": meta(1, "measure"),
            "min_contrast": meta(2, "measure", unit="score"),
            "sigma": meta(3, "measure", unit="px"),
            "bands": meta(2, "measure"),
        },
        rect=("Janela (x0, y0, x1, y1)", "Frações da imagem; ao longo da borda e mais curta que ela"),
        polarity=("Tipo de borda", "Subida: do escuro para o claro da esquerda para a direita (borda vertical) ou de cima para baixo (borda horizontal)", {"rising": "subida (escuro→claro)", "falling": "descida (claro→escuro)"}),
        min_contrast=("Contraste mínimo", "Altura do degrau em níveis de cinza (0 a 255)"),
        sigma=("Suavização (px)", "Pelo menos 0,5"),
        bands=("Faixas", "Quantas faixas dão um ponto da borda cada uma"),
    ))

    rect: Rect
    polarity: Literal["rising", "falling"]
    min_contrast: Annotated[float, Field(ge=1, le=255)] = 20
    sigma: Annotated[float, Field(ge=0.5, le=20)] = 1.0
    bands: Annotated[int, Field(ge=3, le=41)] = 7

    @model_validator(mode="after")
    def _window(self) -> Self:
        if not (self.rect[0] < self.rect[2] and self.rect[1] < self.rect[3]):
            raise ValueError("rect must be [x0, y0, x1, y1] with x0 < x1 and y0 < y1")
        return self


class EdgesParams(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra=labels(
        "O objeto é o canto de duas bordas retas; a âncora tem a posição e o ângulo dele.",
        meta={
            "vertical": meta(1, "measure"),
            "horizontal": meta(1, "measure"),
            "taught_rect": meta(1, "measure", widget="region"),
            "taught_corner": meta(1, "measure"),
        },
        vertical=("Borda vertical", "Varre da esquerda para a direita"),
        horizontal=("Borda horizontal", "Varre de cima para baixo"),
        taught_rect=("Caixa ensinada (x0, y0, x1, y1)", "Onde o objeto está na imagem de referência, em frações da imagem"),
        taught_corner=("Canto ensinado (x, y)", "Onde o canto das duas bordas está na imagem de referência, em frações da imagem"),
    ))

    vertical: CaliperBox
    horizontal: CaliperBox
    taught_rect: Rect
    taught_corner: tuple[Fraction, Fraction]

    @model_validator(mode="after")
    def _box(self) -> Self:
        if not (self.taught_rect[0] < self.taught_rect[2] and self.taught_rect[1] < self.taught_rect[3]):
            raise ValueError("taught_rect must be [x0, y0, x1, y1] with x0 < x1 and y0 < y1")
        return self


def _line(image: np.ndarray, box: CaliperBox, scans: Literal["x", "y"]) -> tuple[float, float, float] | None:
    """The line of an edge as `along = slope * across + offset` (`across` is the coordinate the bands are cut along, `along` the one
    that is scanned), in frame pixels at the boundary of pixels, and the share of the bands that found it. None without a line."""
    height, width = image.shape[:2]
    x0, y0, x1, y1 = round(box.rect[0] * width), round(box.rect[1] * height), round(box.rect[2] * width), round(box.rect[3] * height)
    window = image[y0:y1, x0:x1]
    scan_len, band_len = (window.shape[1], window.shape[0]) if scans == "x" else (window.shape[0], window.shape[1])
    if scan_len < MIN_WINDOW or band_len < box.bands:
        return None
    cuts = np.linspace(0, band_len, box.bands + 1).round().astype(int)
    points: list[tuple[float, float]] = []  # (across, along)
    for lo, hi in zip(cuts[:-1], cuts[1:], strict=True):
        if hi <= lo:
            continue
        band = window[:, lo:hi] if scans == "y" else window[lo:hi, :]
        edges = [e for e in find_edges(profile(band, scans), box.sigma, box.polarity, box.min_contrast)]
        if not edges:
            continue
        best = max(edges, key=lambda e: e.contrast)
        origin_along, origin_across = (x0, y0) if scans == "x" else (y0, x0)
        points.append((origin_across + (lo + hi) / 2, origin_along + best.position + 0.5))
    if len(points) < max(3, box.bands // 2):
        return None
    xy = np.array(points)
    keep = np.ones(len(xy), bool)
    for _ in range(3):  # a false edge in one band must not tilt the line
        if keep.sum() < 3:
            return None
        slope, offset = np.polyfit(xy[keep, 0], xy[keep, 1], 1)
        residual = np.abs(xy[:, 1] - (slope * xy[:, 0] + offset))
        spread = 1.4826 * float(np.median(np.abs(residual[keep] - np.median(residual[keep]))))
        wanted = residual <= max(3 * spread, 1.0)
        if (wanted == keep).all():
            break
        keep = wanted
    if keep.sum() < max(3, box.bands // 2):
        return None
    return float(slope), float(offset), float(keep.sum() / box.bands)


def locate(frame: np.ndarray, params: EdgesParams, files: JobFiles) -> Fixture | None:
    height, width = frame.shape[:2]
    a = _line(frame, params.vertical, "x")  # x = a_slope * y + a_offset
    b = _line(frame, params.horizontal, "y")  # y = b_slope * x + b_offset
    if a is None or b is None:
        return None
    (sa, oa, ca), (sb, ob, cb) = a, b
    angle_a, angle_b = math.degrees(math.atan(sa)), -math.degrees(math.atan(sb))  # the turn of each edge, counter-clockwise
    skew = abs(angle_a - angle_b)
    if skew > MAX_SKEW:
        return None
    denominator = 1 - sa * sb
    corner_x = (sa * ob + oa) / denominator
    corner_y = sb * corner_x + ob
    angle = (angle_a + angle_b) / 2
    # the taught box goes where the corner is, turned as the edges are
    (tx0, ty0, tx1, ty1), (kx, ky) = params.taught_rect, params.taught_corner
    vx, vy = ((tx0 + tx1) / 2 - kx) * width, ((ty0 + ty1) / 2 - ky) * height
    c, s = math.cos(math.radians(angle)), math.sin(math.radians(angle))
    cx, cy = corner_x + vx * c + vy * s, corner_y - vx * s + vy * c
    w, h = (tx1 - tx0) * width, (ty1 - ty0) * height
    rect = ((cx - w / 2) / width, (cy - h / 2) / height, (cx + w / 2) / width, (cy + h / 2) / height)
    return Fixture(rect=rect, angle=angle, scale=1.0, score=float(min(ca, cb) * max(0.0, 1 - skew / MAX_SKEW)))


EDGES = register(LocatorType(name="edges", version=1, params=EdgesParams, locate=locate))
