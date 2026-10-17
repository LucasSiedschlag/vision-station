"""What a job keeps to prove, later, that it still behaves the same (architecture §4.1, §4.2).

    reference/reference.png          the view of a good object when the job was saved
    reference/reference.meta.yaml    brightness, sharpness and anchor position measured on it
    tests/expected.yaml              the reference set: image -> expected result
    tests/images/*.png               the reference set's images
"""

from collections.abc import Callable
from typing import Annotated, Literal

import cv2
import numpy as np
import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from vision_station.store.errors import FormatError
from vision_station.algorithms import metrics

REFERENCE_IMAGE = "reference/reference.png"
REFERENCE_META = "reference/reference.meta.yaml"
EXPECTED_FILE = "tests/expected.yaml"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ReferenceMeta(_Strict):
    brightness: float
    sharpness: float
    anchor: tuple[float, float] | None = None  # centre of the located anchor, as fractions of the frame


class ExpectedCase(_Strict):
    image: str
    outcome: Literal["PASS", "FAIL", "ERROR"]
    scores: dict[str, float] = {}  # per tool id; compared within `tolerance`
    reason_contains: str | None = None


class Expected(_Strict):
    tolerance: Annotated[float, Field(ge=0)] = 0.05
    cases: Annotated[list[ExpectedCase], Field(min_length=1)]


def parse_expected(data: bytes) -> Expected:
    try:
        return Expected.model_validate(yaml.safe_load(data))
    except (ValidationError, yaml.YAMLError) as exc:
        raise FormatError(f"{EXPECTED_FILE} is not valid: {exc}") from exc


def parse_meta(data: bytes) -> ReferenceMeta:
    try:
        return ReferenceMeta.model_validate(yaml.safe_load(data))
    except (ValidationError, yaml.YAMLError) as exc:
        raise FormatError(f"{REFERENCE_META} is not valid: {exc}") from exc


def decode_image(data: bytes) -> np.ndarray | None:
    image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    return image


def make_reference_files(
    image: np.ndarray,
    locate: Callable[[np.ndarray], tuple[float, float] | None] | None = None,
) -> dict[str, bytes]:
    """The two reference files for a job, from a view of a good object. Add them to the job's extra files."""
    ok, png = cv2.imencode(".png", image)
    if not ok:
        raise ValueError("cannot encode the reference image")
    meta = ReferenceMeta(
        brightness=metrics.brightness(image),
        sharpness=metrics.sharpness(image),
        anchor=locate(image) if locate else None,
    )
    return {
        REFERENCE_IMAGE: png.tobytes(),
        REFERENCE_META: yaml.safe_dump(meta.model_dump(mode="json"), sort_keys=False).encode("utf-8"),
    }
