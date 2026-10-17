"""The picture of a result: the frame with the anchor and every tool's region drawn."""

import cv2
import numpy as np

from vision_station.core.results import InspectionResult

_GREEN, _RED, _YELLOW = (60, 190, 60), (50, 50, 230), (0, 200, 240)


def draw_overlay(image: np.ndarray, result: InspectionResult) -> np.ndarray:
    """A copy of the frame with the anchor and every tool's region drawn: green passed, red failed."""
    out = image.copy() if image.ndim == 3 else cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    h, w = out.shape[:2]
    thick = max(2, round(max(h, w) / 400))
    anchor = result.details.get("anchor")
    if anchor:
        x0, y0, x1, y1 = anchor["rect"]
        cv2.rectangle(out, (round(x0 * w), round(y0 * h)), (round(x1 * w), round(y1 * h)), _YELLOW, thick)
    for region in result.details.get("regions", []):
        x0, y0, x1, y1 = region["rect"]
        # an informative tool that fails is marked, but not in the colour of a failure (it decides nothing)
        color = _GREEN if region["passed"] else _RED if region.get("affects_result", True) else _YELLOW
        cv2.rectangle(out, (x0, y0), (x1 - 1, y1 - 1), color, thick)
        cv2.putText(out, region["tool"], (x0 + 4, y0 + 8 + 10 * thick), cv2.FONT_HERSHEY_SIMPLEX, 0.3 * thick, color, thick)
    return out
