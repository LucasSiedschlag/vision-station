"""The model card (architecture §9, FR-MDL-3): what a model in a job is, read from its YAML.

    models/defects.card.yaml    what it is: task, classes, input, outputs, SHA-256, licences, metrics
"""

from typing import Annotated, Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

CARD_FORMAT = 1


class ModelError(Exception):
    """The model cannot be used: no card, a wrong checksum, an unexpected shape."""


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class InputSpec(_Strict):
    size: tuple[Annotated[int, Field(gt=0)], Annotated[int, Field(gt=0)]]  # height, width of the model input
    channels: Literal["RGB", "BGR"] = "RGB"
    scale: Annotated[float, Field(gt=0)] = 255.0  # pixel values are divided by this first
    mean: tuple[float, float, float] = (0.0, 0.0, 0.0)  # then (x - mean) / std, per channel
    std: tuple[float, float, float] = (1.0, 1.0, 1.0)
    keep_aspect: bool = False  # True: letterbox (pad) instead of stretching


class OutputSpec(_Strict):
    softmax: bool = False  # classifier: the output is logits
    boxes: str | None = None  # detector: name of the boxes output (default: the first)
    scores: str | None = None  # detector: name of the logits output (default: the second)
    sigmoid: bool = True  # detector: the scores are logits


class ModelCard(_Strict):
    format: Literal[1]
    task: Literal["classifier", "detector", "anomaly"]
    sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    classes: list[str] = []  # classifier and detector
    input: InputSpec
    output: OutputSpec = OutputSpec()
    threshold: float | None = None  # anomaly: score above this is anomalous
    name: str = ""
    trained_at: str = ""
    dataset_id: str = ""
    licence_code: str = ""  # e.g. "Apache-2.0 (RF-DETR)"
    licence_weights: str = ""  # of the starting weights (TD-08)
    metrics: dict[str, Any] = {}


def parse_card(data: bytes) -> ModelCard:
    try:
        return ModelCard.model_validate(yaml.safe_load(data))
    except (ValidationError, yaml.YAMLError) as exc:
        raise ModelError(f"model card is not valid: {exc}") from exc
