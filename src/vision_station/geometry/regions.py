"""Regions of a job in the picture (architecture §7.1): a region relative to the frame or to the anchor."""

from vision_station.jobs import Job
from vision_station.locators import Anchor

PixelRect = tuple[int, int, int, int]  # x0, y0, x1, y1


class RegionError(Exception):
    """The region cannot be cut from the picture; carries the ERROR text for the operator."""


def resolve_roi(job: Job, name: str, anchor: Anchor | None, shape: tuple[int, ...]) -> tuple[tuple[float, float, float, float], PixelRect]:
    """The region `name` as fractions of the frame and as pixels. Raises RegionError if it cannot be cut."""
    if name == "frame":
        rect = (0.0, 0.0, 1.0, 1.0)
    elif name == "anchor":
        if anchor is None:
            raise RegionError("Região 'anchor' sem localizador")
        rect = anchor.rect
    else:
        roi = job.geometry.rois[name]
        if roi.relative_to == "frame":
            rect = roi.rect
        else:
            if anchor is None:
                raise RegionError(f"Região '{name}' depende do objeto, que não foi localizado")
            ax0, ay0, ax1, ay1 = anchor.rect
            w, h = ax1 - ax0, ay1 - ay0
            x0, y0, x1, y1 = roi.rect
            rect = (ax0 + x0 * w, ay0 + y0 * h, ax0 + x1 * w, ay0 + y1 * h)
    height, width = shape[:2]
    px = (round(rect[0] * width), round(rect[1] * height), round(rect[2] * width), round(rect[3] * height))
    if px[2] - px[0] < 1 or px[3] - px[1] < 1 or px[0] < 0 or px[1] < 0 or px[2] > width or px[3] > height:
        raise RegionError(f"Região '{name}' fora da imagem")
    return rect, px
