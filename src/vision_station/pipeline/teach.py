"""Teaching the variation model of a `compare` tool from pictures of good parts (VIA-0075 CP1, TD-25).

The pictures go through the same steps as an inspection until the region: the fixtures are located and the region of the tool is cut upright,
so what is taught is what the tool will be given. A picture whose fixture is not found, or whose region cannot be cut, is **listed as skipped
with the reason**, never dropped in silence. A region cut from a fixture of another scale is resampled to the size it has at scale 1, which is
the size the model is taught on.
"""

from collections.abc import Sequence
from dataclasses import dataclass

import cv2
import numpy as np

from vision_station.algorithms import variation
from vision_station.core.i18n import render
from vision_station.geometry.regions import RegionError, cut_region
from vision_station.pipeline.inspect import locate_fixtures
from vision_station.store.bundle import JobBundle


@dataclass(frozen=True)
class Skipped:
    name: str
    reason: str


@dataclass(frozen=True)
class Taught:
    data: bytes  # the file of the model, `models/<name>.var`
    used: int
    skipped: tuple[Skipped, ...]
    size: tuple[int, int]  # width and height of the region the model was taught on


def teach_tool(bundle: JobBundle, tool_id: str, pictures: Sequence[tuple[str, np.ndarray]]) -> Taught:
    """The model of the region of tool `tool_id` from `pictures` (name, frame). Raises `ValueError` when the tool is not in the job or fewer than
    3 pictures remain once the ones that cannot be used are skipped."""
    job = bundle.job
    tool = next((t for t in job.tools if t.id == tool_id), None)
    if tool is None:
        raise ValueError(f"the job has no tool '{tool_id}'")
    regions: list[np.ndarray] = []
    skipped: list[Skipped] = []
    size: tuple[int, int] | None = None
    for name, frame in pictures:
        fixtures, stop = locate_fixtures(bundle, frame)
        if stop is not None:
            skipped.append(Skipped(name, render(stop.text)))
            continue
        try:
            region = cut_region(job, tool.roi, fixtures, frame)
        except RegionError as exc:
            skipped.append(Skipped(name, render(exc.text)))
            continue
        relative = tool.roi if tool.roi in fixtures else getattr(job.geometry.rois.get(tool.roi), "relative_to", "frame")
        scale = fixtures[relative].scale if relative in fixtures else 1.0
        image = region.image
        if scale != 1.0:  # the size the region has when the part is as large as taught
            image = cv2.resize(image, (max(1, round(image.shape[1] / scale)), max(1, round(image.shape[0] / scale))), interpolation=cv2.INTER_AREA)
        if size is None:
            size = (image.shape[1], image.shape[0])
        elif (image.shape[1], image.shape[0]) != size:
            image = cv2.resize(image, size, interpolation=cv2.INTER_AREA)
        regions.append(image)
    if len(regions) < variation.MIN_IMAGES:
        why = "; ".join(f"{s.name}: {s.reason}" for s in skipped)
        raise ValueError(f"only {len(regions)} of {len(pictures)} pictures can be used, at least {variation.MIN_IMAGES} are needed" + (f" ({why})" if why else ""))
    return Taught(variation.teach(regions), len(regions), tuple(skipped), size or (0, 0))
