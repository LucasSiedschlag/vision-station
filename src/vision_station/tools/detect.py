"""Detect tool: runs a trained model on the region (TD-08, TD-09, architecture §9).

The model and its card are files inside the job (`models/<name>.onnx`, `models/<name>.card.yaml`); the card
says the task. What fails:

- classifier: the top class is one of `fail_classes`, or not one of `pass_classes` (when given), or its
  probability is below `min_confidence` (unsure is a failure, never a pass).
- detector: any box of a class in `fail_classes`; or a class of `require_classes` with no box; or more
  boxes of `count_class` than `max_count` / fewer than `min_count`.
- anomaly: the score is above `threshold` (the tool's, else the card's).

Fields for `reason_fail`: {label}, {confidence}, {classes} (the classes found, joined by ", "), {count},
{score}, {threshold}.
"""

from typing import Annotated, Self

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

from vision_station.core.i18n import text_of
from vision_station.core.jobfiles import JobFileError, JobFiles
from vision_station.models import ModelError, parse_card, predict
from vision_station.core.schema_labels import labels
from vision_station.algorithms.measures import at_most
from vision_station.core.results import Criterion, Unit
from vision_station.tools.base import ToolError, ToolResult, ToolType, count_at_most, judged, minimum, register, rule


class DetectParams(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra=labels(
        "Roda um modelo treinado na região.",
        model=("Modelo", "Arquivo .onnx dentro do job (treinado fora da estação)"),
        card=("Cartão do modelo", "Vazio: o mesmo nome com .card.yaml"),
        min_confidence=("Confiança mínima", "0 a 1"),
        fail_classes=("Classes que reprovam", "Ex.: risco, amassado"),
        pass_classes=("Classes que aprovam (classificador)", "Vazio: qualquer classe que não reprove"),
        require_classes=("Classes obrigatórias (detector)", "Precisa haver pelo menos uma de cada"),
        count_class=("Classe contada (detector)", ""),
        min_count=("Mínimo da classe contada", ""),
        max_count=("Máximo da classe contada", ""),
        threshold=("Limite de anomalia", "Vazio: o do cartão do modelo"),
    ))

    model: Annotated[str, Field(min_length=1)]
    card: str | None = None
    min_confidence: Annotated[float, Field(ge=0, le=1)] = 0.5
    fail_classes: list[str] = []
    pass_classes: list[str] = []
    require_classes: list[str] = []
    count_class: str | None = None
    min_count: Annotated[int, Field(ge=0)] | None = None
    max_count: Annotated[int, Field(ge=0)] | None = None
    threshold: float | None = None

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if (self.min_count is not None or self.max_count is not None) and not self.count_class:
            raise ValueError("min_count and max_count need count_class")
        return self

    @property
    def card_path(self) -> str:
        if self.card:
            return self.card
        stem = self.model[: -len(".onnx")] if self.model.endswith(".onnx") else self.model
        return f"{stem}.card.yaml"


def run(region: np.ndarray, params: DetectParams, files: JobFiles) -> ToolResult:
    try:
        card = parse_card(files.bytes(params.card_path))
        prediction = predict(files.bytes(params.model), card, region, params.min_confidence)
    except (ModelError, JobFileError) as exc:
        raise ToolError(text_of(exc)) from exc
    values: dict = {"label": None, "confidence": None, "classes": "", "count": None, "score": None, "threshold": None}
    details: dict = {"task": card.task, "model": card.name or params.model}
    criteria: list[Criterion] = []
    units: dict[str, Unit] = {}

    if card.task == "classifier":
        label, conf = prediction.label or "", prediction.confidence
        values.update(label=label, confidence=conf, classes=label)
        details.update(label=label, confidence=conf, probabilities=prediction.probabilities)
        bad = label in params.fail_classes or (params.pass_classes and label not in params.pass_classes)
        criteria.append(rule("class", 0.0 if bad else 1.0))
        criteria.append(minimum("min_confidence", "confidence", conf, params.min_confidence))  # unsure is a failure
        units["confidence"] = "fraction"

    elif card.task == "detector":
        found = prediction.detections
        classes = sorted({d.label for d in found})
        values["classes"] = ", ".join(classes)
        details["detections"] = [{"label": d.label, "confidence": d.confidence, "box": list(d.box)} for d in found]
        failing = [d for d in found if d.label in params.fail_classes]
        if params.fail_classes:
            criteria.append(rule("fail_class", max(0.0, 1.0 - max(d.confidence for d in failing)) if failing else 1.0))
        missing = [c for c in params.require_classes if c not in classes]
        if params.require_classes:
            criteria.append(rule("require_classes", 0.0 if missing else 1.0))
        if missing:
            details["missing"] = missing
        if params.count_class:
            count = sum(d.label == params.count_class for d in found)
            values["count"] = count
            units["count"] = "count"
            if params.min_count is not None:
                criteria.append(minimum("min_count", "count", count, params.min_count))
            if params.max_count is not None:
                criteria.append(count_at_most("max_count", "count", count, params.max_count))

    else:  # anomaly
        threshold = params.threshold if params.threshold is not None else card.threshold
        if threshold is None:
            raise ToolError("anomaly model without a threshold: set it in the tool or in the model card")
        score = float(prediction.score or 0.0)
        values.update(score=score, threshold=threshold)
        details.update(score=score, threshold=threshold)
        units["score"] = "score"
        part = 1.0 if score <= threshold else max(0.0, at_most(score / (threshold * 2 or 1), 0.5))
        criteria.append(Criterion("max_score", "max", part >= 1.0, part, "score", score, float(threshold)))

    return judged(criteria, values=values, details=details, units=units)


DETECT = register(ToolType(name="detect", version=1, params=DetectParams, run=run, needs=lambda p: [p.model, p.card_path]))
