"""The detect tool with real (tiny) ONNX models built here: a classifier, a DETR-style detector, an anomaly scorer."""

import hashlib

import numpy as np
import onnx
import pytest
import yaml
from onnx import TensorProto, helper, numpy_helper

from vision_station.models import ModelError, parse_card, predict
from vision_station.tools import ToolError, run_tool

RED, BLUE, GRAY = (30, 30, 220), (220, 60, 30), (128, 128, 128)  # BGR
W = np.array([[4.0, -4.0], [0.0, 0.0], [-4.0, 4.0]], np.float32)  # RGB means -> [red, blue] scores


def _model(nodes, outputs, initializers=()):
    graph = helper.make_graph(nodes, "m", [helper.make_tensor_value_info("x", TensorProto.FLOAT, [1, 3, 8, 8])], outputs, list(initializers))
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 17)])
    model.ir_version = 9
    onnx.checker.check_model(model)
    return model.SerializeToString()


def classifier() -> bytes:
    return _model(
        [helper.make_node("ReduceMean", ["x"], ["m"], axes=[2, 3], keepdims=0), helper.make_node("MatMul", ["m", "w"], ["y"])],
        [helper.make_tensor_value_info("y", TensorProto.FLOAT, [1, 2])],
        [numpy_helper.from_array(W, "w")],
    )


def detector() -> bytes:
    boxes = numpy_helper.from_array(np.array([[[0.5, 0.5, 0.5, 0.5]]], np.float32), "b")
    return _model(
        [
            helper.make_node("ReduceMean", ["x"], ["m"], axes=[2, 3], keepdims=0),
            helper.make_node("MatMul", ["m", "w"], ["s"]),
            helper.make_node("Reshape", ["s", "shape"], ["logits"]),
            helper.make_node("Identity", ["b"], ["dets"]),
        ],
        [helper.make_tensor_value_info("dets", TensorProto.FLOAT, [1, 1, 4]), helper.make_tensor_value_info("logits", TensorProto.FLOAT, [1, 1, 2])],
        [numpy_helper.from_array(W, "w"), numpy_helper.from_array(np.array([1, 1, 2], np.int64), "shape"), boxes],
    )


def anomaly() -> bytes:
    return _model([helper.make_node("ReduceMax", ["x"], ["score"], keepdims=0)], [helper.make_tensor_value_info("score", TensorProto.FLOAT, [])])


def card(model: bytes, task: str, **extra) -> bytes:
    data = {"format": 1, "task": task, "sha256": hashlib.sha256(model).hexdigest(), "input": {"size": [8, 8]}, "name": f"teste {task}", **extra}
    return yaml.safe_dump(data).encode()


def files(model: bytes, task: str, **extra) -> dict[str, bytes]:
    return {"models/m.onnx": model, "models/m.card.yaml": card(model, task, **extra)}


def patch(colour, size=(40, 40)):
    return np.full((*size, 3), colour, np.uint8)


def detect(region, f, **params):
    return run_tool("detect", 1, region, {"model": "models/m.onnx", **params}, f)


def test_classifier_passes_and_fails_by_class():
    f = files(classifier(), "classifier", classes=["vermelho", "azul"], output={"softmax": True})
    ok = detect(patch(BLUE), f, fail_classes=["vermelho"])
    assert ok.passed and ok.score == 1.0 and ok.values["label"] == "azul" and ok.values["confidence"] > 0.9
    bad = detect(patch(RED), f, fail_classes=["vermelho"])
    assert not bad.passed and bad.values["label"] == "vermelho"
    assert bad.reason("Cor errada: {label} ({confidence:.0%})").startswith("Cor errada: vermelho (")
    assert not detect(patch(RED), f, pass_classes=["azul"]).passed


def test_an_unsure_classifier_is_a_failure():
    f = files(classifier(), "classifier", classes=["vermelho", "azul"], output={"softmax": True})
    r = detect(patch(GRAY), f, min_confidence=0.9)  # gray: 50/50
    assert not r.passed and 0 < r.score < 1


def test_detector_finds_boxes_and_fails_on_a_fail_class_or_a_missing_one():
    f = files(detector(), "detector", classes=["risco", "tampa"])
    bad = detect(patch(RED), f, fail_classes=["risco"])
    assert not bad.passed and bad.values["classes"] == "risco"
    assert bad.details["detections"][0]["box"] == pytest.approx([0.25, 0.25, 0.75, 0.75])
    assert detect(patch(BLUE), f, fail_classes=["risco"]).passed
    assert not detect(patch(BLUE), f, require_classes=["risco"]).passed
    counted = detect(patch(BLUE), f, count_class="tampa", min_count=2)
    assert not counted.passed and counted.values["count"] == 1


def test_anomaly_score_against_the_threshold_of_the_card_or_the_tool():
    f = files(anomaly(), "anomaly", threshold=0.6)
    dark = detect(patch((40, 40, 40)), f)
    assert dark.passed and dark.values["score"] == pytest.approx(40 / 255, abs=0.01)
    bright = detect(patch((250, 250, 250)), f)
    assert not bright.passed and bright.reason("Anomalia {score:.2f} > {threshold}") == "Anomalia 0.98 > 0.6"
    assert detect(patch((250, 250, 250)), f, threshold=0.99).passed
    with pytest.raises(ToolError, match="threshold"):
        detect(patch(GRAY), files(anomaly(), "anomaly"))


def test_a_model_that_is_not_the_one_of_its_card_is_refused():
    f = files(classifier(), "classifier")
    f["models/m.onnx"] = detector()
    with pytest.raises(ToolError, match="SHA-256"):
        detect(patch(RED), f)


def test_card_problems_are_errors():
    with pytest.raises(ModelError, match="card"):
        parse_card(b"format: 1\ntask: segmenter\n")
    model = classifier()
    with pytest.raises(ModelError, match="classes"):
        predict(model, parse_card(card(model, "classifier", classes=["a", "b", "c"])), patch(RED))
    with pytest.raises(ToolError, match="not in the job"):
        detect(patch(RED), {"models/m.onnx": model})


def test_letterbox_maps_boxes_back_to_the_region():
    f = files(detector(), "detector", classes=["risco", "tampa"], input={"size": [8, 8], "keep_aspect": True})
    r = detect(patch(RED, size=(20, 40)), f, fail_classes=["risco"])  # wide region: padded above and below
    x0, y0, x1, y1 = r.details["detections"][0]["box"]
    assert (x0, x1) == pytest.approx((0.25, 0.75)) and y0 == 0.0 and y1 == 1.0  # the middle half of the input is the whole height


def test_in_a_job_the_files_are_required_and_the_pipeline_runs_it():
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).parent))
    from test_verification import FIXTURES, make_bundle
    from vision_station.cameras import Frame
    from vision_station.jobs import Job
    from vision_station.pipeline import inspect_job
    from vision_station.results import Outcome
    from vision_station.store import JobBundle
    from vision_station.store.bundle import bundle_from_files
    from vision_station.store.errors import FormatError
    from vision_station.verification import make_reference_files

    assert FIXTURES
    base = make_bundle()
    data = base.job.model_dump(mode="json")
    data["tools"] = [{"id": "cor", "type": "detect", "version": 1, "roi": "label", "params": {"model": "models/m.onnx", "fail_classes": ["vermelho"]}, "reason_fail": "Peça {label}"}]
    f = files(classifier(), "classifier", classes=["vermelho", "azul"], output={"softmax": True})
    reference = np.tile(np.array([BLUE, (200, 200, 200)], np.uint8)[np.indices((240, 320)).sum(0) % 2], 1)  # sharp, blue-ish checker
    bundle = JobBundle(Job.model_validate(data), base.profile, {**make_reference_files(reference), **f})
    assert bundle_from_files(bundle.files()).job == bundle.job
    with pytest.raises(FormatError, match="m.card.yaml"):
        bundle_from_files({k: v for k, v in bundle.files().items() if k != "models/m.card.yaml"})
    red = reference.copy()
    red[reference[..., 0] == BLUE[0]] = RED
    assert inspect_job(bundle, Frame(reference, 0.0)).outcome is Outcome.PASS
    failed = inspect_job(bundle, Frame(red, 0.0))
    assert failed.outcome is Outcome.FAIL and failed.reason == "Peça vermelho"
