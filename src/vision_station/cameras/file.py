"""Camera driver that replays images from a folder.

Used by automated tests, the verifier's reference-set run and demos without a
camera (architecture §5.3).
"""

import time
from collections import deque
from collections.abc import Callable, Iterator, Mapping
from pathlib import Path
from typing import Any

import cv2

from vision_station.cameras.base import (
    SETTINGS,
    ApplyReport,
    Camera,
    CameraError,
    Capabilities,
    Frame,
    Health,
    SettingStatus,
)
from vision_station.jobs import CameraProfile

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp"}


class FileCamera(Camera):
    """Delivers the images of a folder in name order.

    connection: {"path": folder}. With `loop=True` the sequence repeats forever,
    otherwise `frames()` ends after the last image.
    """

    def __init__(self, loop: bool = False, clock: Callable[[], float] = time.monotonic):
        self._loop = loop
        self._clock = clock
        self._paths: list[Path] = []
        self._open = False
        self._stamps: deque[float] = deque(maxlen=30)

    def open(self, connection: Mapping[str, Any]) -> None:
        folder = Path(connection["path"])
        if not folder.is_dir():
            raise CameraError(f"folder not found: {folder}")
        self._paths = sorted(p for p in folder.iterdir() if p.suffix.lower() in IMAGE_SUFFIXES)
        if not self._paths:
            raise CameraError(f"no images in {folder}")
        self._stamps.clear()
        self._open = True

    def close(self) -> None:
        self._open = False

    def capabilities(self) -> Capabilities:
        return Capabilities(has_snapshot=True)

    def apply(self, profile: CameraProfile, raw: Mapping[str, bytes] | None = None) -> ApplyReport:
        self._require_open()
        return ApplyReport(
            status=dict.fromkeys(SETTINGS, SettingStatus.NOT_SUPPORTED),
            detail=dict.fromkeys(SETTINGS, "file camera has no settings"),
        )

    def read_back(self) -> dict[str, Any]:
        self._require_open()
        return {}

    def frames(self) -> Iterator[Frame]:
        self._require_open()
        while self._open:
            for path in self._paths:
                if not self._open:
                    return
                yield self._read(path)
            if not self._loop:
                return

    def snapshot(self) -> Frame | None:
        self._require_open()
        return self._read(self._paths[0])

    def health(self) -> Health:
        age = self._clock() - self._stamps[-1] if self._stamps else None
        fps = 0.0
        if len(self._stamps) > 1 and self._stamps[-1] > self._stamps[0]:
            fps = (len(self._stamps) - 1) / (self._stamps[-1] - self._stamps[0])
        return Health(connected=self._open, fps=fps, last_frame_age_s=age)

    def _read(self, path: Path) -> Frame:
        image = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if image is None:
            raise CameraError(f"cannot read image: {path}")
        stamp = self._clock()
        self._stamps.append(stamp)
        return Frame(image=image, timestamp=stamp)

    def _require_open(self) -> None:
        if not self._open:
            raise CameraError("camera is not open")
