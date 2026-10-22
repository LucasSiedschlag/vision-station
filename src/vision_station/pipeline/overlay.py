"""The picture of a result: the frame with the fixtures and every tool's region drawn (turned ones as their outline)."""

import cv2
import numpy as np

from vision_station.core.results import InspectionResult, Mark, ToolReport

_GREEN, _RED, _YELLOW, _GRAY = (60, 190, 60), (50, 50, 230), (0, 200, 240), (160, 160, 160)


def draw_overlay(image: np.ndarray, result: InspectionResult) -> np.ndarray:
    """A copy of the frame with the anchor and every tool's region drawn: green passed, red failed."""
    out = image.copy() if image.ndim == 3 else cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    h, w = out.shape[:2]
    thick = max(2, round(max(h, w) / 400))
    for fixture in result.details.get("fixtures") or ([result.details["anchor"]] if result.details.get("anchor") else []):
        if "corners" in fixture:
            cv2.polylines(out, [np.round(np.array(fixture["corners"])).astype(np.int32)], True, _YELLOW, thick)
        else:
            x0, y0, x1, y1 = fixture["rect"]
            cv2.rectangle(out, (round(x0 * w), round(y0 * h)), (round(x1 * w), round(y1 * h)), _YELLOW, thick)
    for region in result.details.get("regions", []):
        x0, y0, x1, y1 = region["rect"]
        # an informative tool that fails is marked, but not in the colour of a failure (it decides nothing)
        color = _GREEN if region["passed"] else _RED if region.get("affects_result", True) else _YELLOW
        if "corners" in region:
            cv2.polylines(out, [np.round(np.array(region["corners"])).astype(np.int32)], True, color, thick)
        else:
            cv2.rectangle(out, (x0, y0), (x1 - 1, y1 - 1), color, thick)
        cv2.putText(out, region["tool"], (x0 + 4, y0 + 8 + 10 * thick), cv2.FONT_HERSHEY_SIMPLEX, 0.3 * thick, color, thick)
    for tool in result.tools:
        for mark in tool.marks:
            _draw_mark(out, mark, tool, thick)
    return out


def _draw_mark(out: np.ndarray, mark: Mark, tool: ToolReport, thick: int) -> None:
    """One mark of a tool, whose points are fractions of the frame: the colour comes from its role, and what a tool found
    takes the verdict of the tool (the same rule as the screen, docs/frontend.md §18)."""
    h, w = out.shape[:2]
    points = np.round(np.array([[x * w, y * h] for x, y in mark.points])).astype(np.int32)
    failed = mark.role == "defect" or (mark.role == "found" and not tool.passed)
    # an informative tool never decides, so what makes it fail is not drawn as the failure of the part (FR-INS-13)
    color = _GRAY if mark.role == "expected" else (_RED if tool.affects_result else _YELLOW) if failed else _GREEN
    if mark.kind == "rect":
        cv2.rectangle(out, tuple(points[0]), tuple(points[1]), color, thick)
    elif mark.kind == "poly":
        cv2.polylines(out, [points], mark.closed, color, thick)
    elif mark.kind == "point":
        x, y = points[0]
        arm = 3 * thick
        cv2.line(out, (x - arm, y), (x + arm, y), color, thick)
        cv2.line(out, (x, y - arm), (x, y + arm), color, thick)
    else:
        cv2.putText(out, mark.text, tuple(points[0]), cv2.FONT_HERSHEY_SIMPLEX, 0.3 * thick, color, thick)
