"""What every type answers for its case's pictures, as plain data. Run as a process by the V9 test (`python -m validation.probe`)."""

import dataclasses
import json
import sys
from collections.abc import Mapping

import numpy as np

from validation.registry import TYPES, case_for
from vision_station.locators import run_locator
from vision_station.tools import ToolError, run_tool
from vision_station.locators import LocatorError


def plain(value):
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {f.name: plain(getattr(value, f.name)) for f in dataclasses.fields(value)}
    if isinstance(value, Mapping):
        return {str(k): plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    if isinstance(value, np.ndarray):
        return plain(value.tolist())
    if isinstance(value, np.generic):
        return value.item()
    return value


def pictures(kind, case):
    noise = np.random.default_rng(11).integers(0, 256, (90, 120, 3), dtype=np.uint8)
    if kind == "tool":
        return {"passing": case.passing, "failing": case.failing, "noise": noise}
    return {"scene": case.scene.frame, "noise": noise}


def answers() -> dict:
    out = {}
    for kind, name, version in TYPES:
        case = case_for(kind, name, version)
        for label, image in pictures(kind, case).items():
            try:
                if kind == "tool":
                    result = run_tool(name, version, image, case.params, case.files)
                else:
                    result = run_locator(name, version, image, case.params, case.files)
            except (ToolError, LocatorError) as exc:
                result = {"refused": str(exc)}
            out[f"{kind}-{name}-v{version}/{label}"] = plain(result)
    return out


if __name__ == "__main__":
    json.dump(answers(), sys.stdout)
