"""The files a job carries besides job.yaml (templates, models...), as tools and locators see them.

A tool or locator that needs a file names it in its parameters (a path inside the job, e.g.
`locator/template.png`) and lists it in its `needs`, so a job without the file is refused when it is
loaded instead of failing on the first inspection.
"""

from collections.abc import Mapping
from functools import lru_cache

import cv2
import numpy as np
import yaml
from pydantic import ValidationError

from vision_station.core.calibration import CALIBRATION_FILE, Calibration, Scale


class JobFileError(Exception):
    """A file the job refers to is missing or cannot be read."""


@lru_cache(maxsize=32)
def _decode(data: bytes, flags: int) -> np.ndarray | None:
    # bytes cache their hash, so a template used on every inspection is decoded once
    return cv2.imdecode(np.frombuffer(data, np.uint8), flags)


class JobFiles:
    def __init__(self, files: Mapping[str, bytes] | None = None):
        self._files = files or {}

    def __contains__(self, path: str) -> bool:
        return path in self._files

    def bytes(self, path: str) -> bytes:
        try:
            return self._files[path]
        except KeyError:
            raise JobFileError(f"file not in the job: {path}") from None

    def image(self, path: str, gray: bool = False) -> np.ndarray:
        """A decoded image (BGR, or gray). The array is shared: do not change it."""
        image = _decode(self.bytes(path), cv2.IMREAD_GRAYSCALE if gray else cv2.IMREAD_COLOR)
        if image is None:
            raise JobFileError(f"not an image: {path}")
        return image

    @property
    def calibrated(self) -> bool:
        return CALIBRATION_FILE in self._files

    def scale(self) -> Scale:
        """Millimetres per pixel of this job (FR-INS-15). A tool that measures in millimetres asks for it here."""
        if CALIBRATION_FILE not in self._files:
            raise JobFileError(f"the job has no calibration ({CALIBRATION_FILE}): a measure in millimetres needs one")
        return parse_calibration(self._files[CALIBRATION_FILE]).scale


def parse_calibration(data: bytes) -> Calibration:
    try:
        return Calibration.model_validate(yaml.safe_load(data))
    except (ValidationError, yaml.YAMLError) as exc:
        raise JobFileError(f"{CALIBRATION_FILE} is not a valid calibration: {exc}") from exc


def check_files(owner: str, needed: list[str], files: Mapping[str, bytes]) -> None:
    missing = [p for p in needed if p not in files]
    if missing:
        raise JobFileError(f"{owner}: missing files {missing}")
