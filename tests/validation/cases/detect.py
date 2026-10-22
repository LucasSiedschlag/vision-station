import numpy as np

from test_detect_tool import BLUE, RED, classifier, files
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
        Golden("a blue part, red fails", patch(BLUE), passed=True, values={"label": "azul"}),
        Golden("a red part, red fails", patch(RED), passed=False, values={"label": "vermelho"}),
    ),
)}
