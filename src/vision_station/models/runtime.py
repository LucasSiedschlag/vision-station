"""Trained models inside jobs (architecture §9, TD-08, TD-09): an ONNX file and its card.

    models/defects.onnx         the exported model (training happens offline, TD-10)
    models/defects.card.yaml    what it is: task, classes, input, outputs, SHA-256, licences, metrics

The card's SHA-256 must match the file, so a model is never run if it is not the one the job was made
with (FR-MDL-3). Inference uses ONNX Runtime on the CPU; sessions are cached by the model's hash.

Tasks:
- `classifier`: one output [1, C], probabilities or logits (`softmax: true` turns logits into
  probabilities). Result: the class with the highest probability.
- `detector`: DETR-style outputs (RF-DETR): boxes [1, N, 4] as centre-x, centre-y, width, height in
  fractions of the input, and class logits [1, N, C] (sigmoid). Result: every box above the confidence.
- `anomaly`: one output, a score [1] or an anomaly map [1, 1, H, W] whose maximum is the score
  (Anomalib exports). Result: the score; above the card's (or the tool's) threshold is anomalous.
"""

import hashlib
from collections import OrderedDict
from dataclasses import dataclass, field
from threading import Lock
from typing import Any

import cv2
import numpy as np

from vision_station.core.i18n import tr
from vision_station.models.card import InputSpec, ModelCard, ModelError


@dataclass
class Detection:
    label: str
    confidence: float
    box: tuple[float, float, float, float]  # x0, y0, x1, y1 as fractions of the region


@dataclass
class Prediction:
    task: str
    label: str | None = None  # classifier: the top class
    confidence: float = 0.0  # classifier: its probability
    probabilities: dict[str, float] = field(default_factory=dict)
    detections: list[Detection] = field(default_factory=list)
    score: float | None = None  # anomaly


_SESSIONS: "OrderedDict[str, Any]" = OrderedDict()
_LOCK = Lock()


def _session(data: bytes, digest: str) -> Any:
    import onnxruntime as ort  # imported here: jobs without models never load it

    with _LOCK:
        if digest in _SESSIONS:
            _SESSIONS.move_to_end(digest)
            return _SESSIONS[digest]
    options = ort.SessionOptions()
    options.log_severity_level = 3
    try:
        session = ort.InferenceSession(data, sess_options=options, providers=["CPUExecutionProvider"])
    except Exception as exc:  # onnxruntime raises its own exception types
        raise ModelError(f"the model cannot be loaded: {exc}") from exc
    with _LOCK:
        _SESSIONS[digest] = session
        while len(_SESSIONS) > 4:
            _SESSIONS.popitem(last=False)
    return session


def _prepare(image: np.ndarray, spec: InputSpec) -> tuple[np.ndarray, tuple[float, float, float, float]]:
    """The model's input tensor [1, 3, H, W], and the part of it the image fills (for letterboxing)."""
    bgr = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR) if image.ndim == 2 else image
    h, w = spec.size
    if spec.keep_aspect:
        s = min(w / bgr.shape[1], h / bgr.shape[0])
        nw, nh = max(1, round(bgr.shape[1] * s)), max(1, round(bgr.shape[0] * s))
        canvas = np.zeros((h, w, 3), np.uint8)
        x0, y0 = (w - nw) // 2, (h - nh) // 2
        canvas[y0 : y0 + nh, x0 : x0 + nw] = cv2.resize(bgr, (nw, nh), interpolation=cv2.INTER_AREA)
        bgr, area = canvas, (x0 / w, y0 / h, (x0 + nw) / w, (y0 + nh) / h)
    else:
        bgr, area = cv2.resize(bgr, (w, h), interpolation=cv2.INTER_AREA), (0.0, 0.0, 1.0, 1.0)
    pixels = bgr[..., ::-1] if spec.channels == "RGB" else bgr
    x = pixels.astype(np.float32) / spec.scale
    x = (x - np.array(spec.mean, np.float32)) / np.array(spec.std, np.float32)
    return np.ascontiguousarray(x.transpose(2, 0, 1)[None]), area


def _softmax(v: np.ndarray) -> np.ndarray:
    e = np.exp(v - v.max())
    return e / e.sum()


def _sigmoid(v: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-v))


def check_model(model: bytes, card: ModelCard) -> str:
    digest = hashlib.sha256(model).hexdigest()
    if digest != card.sha256:
        raise ModelError("the model file does not match its card (SHA-256): it is not the model this job was made with")
    return digest


def _numbers(value: Any, what: str) -> np.ndarray:
    """An output as numbers, or ModelError: an empty output or a NaN/infinity must never decide a result (a NaN
    is not below any confidence, and argmax takes it as the top class: that was a pass) (VIA-0054)."""
    array = np.asarray(value, np.float64)
    if array.size == 0:
        raise ModelError(tr("saída do modelo vazia ({what})", what=what))
    if not np.all(np.isfinite(array)):
        raise ModelError(tr("saída do modelo não é um número (NaN ou infinito) em {what}", what=what))
    return array


def predict(model: bytes, card: ModelCard, image: np.ndarray, min_confidence: float = 0.5) -> Prediction:
    if image.size == 0:
        raise ModelError("empty region")
    session = _session(model, check_model(model, card))
    tensor, (fx0, fy0, fx1, fy1) = _prepare(image, card.input)
    name = session.get_inputs()[0].name
    outputs = {o.name: v for o, v in zip(session.get_outputs(), session.run(None, {name: tensor}))}
    values = list(outputs.values())

    if card.task == "classifier":
        scores = _numbers(values[0], tr("classes")).reshape(-1)
        if card.classes and len(scores) != len(card.classes):
            raise ModelError(f"the model gives {len(scores)} classes, its card names {len(card.classes)}")
        probs = _numbers(_softmax(scores) if card.output.softmax else scores, tr("probabilidades"))
        names = card.classes or [str(i) for i in range(len(probs))]
        top = int(np.argmax(probs))
        return Prediction("classifier", label=names[top], confidence=float(probs[top]), probabilities={n: float(p) for n, p in zip(names, probs)})

    if card.task == "detector":
        boxes = _numbers(outputs[card.output.boxes] if card.output.boxes else values[0], tr("caixas")).reshape(-1, 4)
        logits = _numbers(outputs[card.output.scores] if card.output.scores else values[1], tr("classes")).reshape(len(boxes), -1)
        if card.classes and logits.shape[1] != len(card.classes):
            # a box of a class past the card's list was dropped in silence: a shifted export could hide the failing class
            raise ModelError(tr("o modelo dá {got} classes e o cartão nomeia {named}", got=logits.shape[1], named=len(card.classes)))
        probs = _sigmoid(logits) if card.output.sigmoid else logits
        names = card.classes or [str(i) for i in range(probs.shape[1])]
        sx, sy = (fx1 - fx0) or 1.0, (fy1 - fy0) or 1.0
        found = []
        for (cx, cy, bw, bh), p in zip(boxes, probs):
            c = int(np.argmax(p))
            if p[c] < min_confidence:
                continue
            box = ((cx - bw / 2 - fx0) / sx, (cy - bh / 2 - fy0) / sy, (cx + bw / 2 - fx0) / sx, (cy + bh / 2 - fy0) / sy)
            found.append(Detection(names[c], float(p[c]), tuple(float(min(1, max(0, v))) for v in box)))  # type: ignore[arg-type]
        found.sort(key=lambda d: d.confidence, reverse=True)
        return Prediction("detector", detections=found)

    return Prediction("anomaly", score=float(_numbers(values[0], tr("pontuação de anomalia")).max()))
