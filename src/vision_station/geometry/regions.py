"""Regions of a job in the picture (architecture §7.1, §14): the whole frame, the box of a fixture, or a region of the
frame or of a fixture, cut out upright for the tool."""

from collections.abc import Mapping

import numpy as np

from vision_station.core.i18n import tr
from vision_station.geometry.pose import Cut, Fixture, RegionOutside, cut
from vision_station.jobs import Job


class RegionError(Exception):
    """The region cannot be cut from the picture; carries the ERROR text for the operator."""

    def __init__(self, text: str):
        super().__init__(text)
        self.text = text  # keeps a Msg: str(exc) would flatten it to Portuguese


def cut_region(job: Job, name: str, fixtures: Mapping[str, Fixture], image: np.ndarray) -> Cut:
    """The region `name` as an upright picture. Raises RegionError if it cannot be cut."""
    try:
        if name == "frame":
            return cut(image, (0.0, 0.0, 1.0, 1.0), None)
        if name in fixtures:  # the whole box of what the locator found, as taught
            return cut(image, (0.0, 0.0, 1.0, 1.0), fixtures[name])
        roi = job.geometry.rois[name]
        return cut(image, roi.rect, None if roi.relative_to == "frame" else fixtures[roi.relative_to])
    except RegionOutside:
        raise RegionError(tr("Região '{name}' fora da imagem", name=name)) from None
    except KeyError:
        raise RegionError(tr("Região '{name}' depende do objeto, que não foi localizado", name=name)) from None
