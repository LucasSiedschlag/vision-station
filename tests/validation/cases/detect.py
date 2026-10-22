import numpy as np

from test_detect_tool import BLUE, RED, anomaly, classifier, detector, files
from validation.case import Case, Golden


def patch(colour):
    return np.full((40, 40, 3), colour, np.uint8)


TOOLS = {1: Case(
    params={"model": "models/m.onnx", "fail_classes": ["vermelho"]},
    files=files(classifier(), "classifier", classes=["vermelho", "azul"], output={"softmax": True}),
    bad_params=({}, {"model": "models/m.onnx", "min_confidence": 2}, {"model": "models/m.onnx", "unknown": 1}),
    passing=patch(BLUE),
    failing=patch(RED),
    goldens=(
        Golden("a blue part, red fails", patch(BLUE), passed=True, values={"label": "azul"}, marks=(("text", "found", (2, 12, 2, 12)),)),
        Golden("a red part, red fails", patch(RED), passed=False, values={"label": "vermelho"}, marks=(("text", "defect", (2, 12, 2, 12)),)),
        Golden("a detector: the box of a fail class is the defect", patch(RED), {"fail_classes": ["risco"]}, files(detector(), "detector", classes=["risco", "tampa"]),
               passed=False, values={"classes": "risco"}, marks=(("rect", "defect", (10, 10, 30, 30)), ("text", "defect", (10, 10, 10, 10)))),
        Golden("a detector: the box of a class that is fine", patch(BLUE), {"fail_classes": ["risco"]}, files(detector(), "detector", classes=["risco", "tampa"]),
               passed=True, marks=(("rect", "found", (10, 10, 30, 30)), ("text", "found", (10, 10, 10, 10)))),
        Golden("an anomaly above the limit flags the whole region", patch((250, 250, 250)), {"model": "models/m.onnx"}, files(anomaly(), "anomaly", threshold=0.6),
               passed=False, marks=(("rect", "defect", (0, 0, 40, 40)),)),
        Golden("an anomaly below the limit draws nothing", patch((40, 40, 40)), {"model": "models/m.onnx"}, files(anomaly(), "anomaly", threshold=0.6), passed=True, marks=()),
    ),
)}
