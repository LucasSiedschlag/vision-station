"""Fixed locator: the object is always in the same place, so the fixture is a rectangle written in the job.

For stations where a jig or a mark holds the object in position, and for jobs that only need a named area.
"""

from typing import Self

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

from vision_station.core.jobfiles import JobFiles
from vision_station.core.schema_labels import labels, meta
from vision_station.geometry.pose import Fixture
from vision_station.locators.base import LocatorType, register


class FixedParams(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra=labels(
        "O objeto fica sempre no mesmo lugar: a âncora é um retângulo escrito no job.",
        meta={"rect": meta(1, "measure", widget="region")},
        rect=("Posição do objeto (x0, y0, x1, y1)", "Frações da imagem; desenhe na imagem")))

    rect: tuple[float, float, float, float] = Field(description="x0, y0, x1, y1 as fractions of the frame")

    @model_validator(mode="after")
    def _valid(self) -> Self:
        x0, y0, x1, y1 = self.rect
        if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
            raise ValueError("rect must be [x0, y0, x1, y1] inside 0..1 with x0 < x1 and y0 < y1")
        return self


def locate(frame: np.ndarray, params: FixedParams, files: JobFiles) -> Fixture:
    return Fixture(rect=params.rect)


FIXED = register(LocatorType(name="fixed", version=1, params=FixedParams, locate=locate))
