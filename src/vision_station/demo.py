"""A simulated station for trying the interface and for the end-to-end tests: no camera, no hardware.

`ScriptedCamera` repeats a scene by the clock (empty, a box slides in, stays, leaves). `ControlledCamera` shows
whatever the caller sets, so a test decides when a box is on the scale.
"""

import time
from collections.abc import Iterator

import cv2
import numpy as np

from vision_station.cameras import ApplyReport, Camera, Capabilities, Frame, Health, SettingStatus
from vision_station.jobs import CameraProfile, Job
from vision_station.store import JobBundle


def scene(box_x: int | None) -> np.ndarray:
    """The station seen from above: a table, and a box with red tape when `box_x` is given."""
    img = np.zeros((540, 960, 3), np.uint8)
    img[:] = (70, 78, 84)
    cv2.rectangle(img, (0, 380), (960, 540), (50, 56, 62), -1)
    cv2.putText(img, "Vision Station demo", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (200, 200, 200), 2)
    if box_x is not None:
        cv2.rectangle(img, (box_x, 160), (box_x + 340, 400), (60, 90, 170), -1)
        cv2.rectangle(img, (box_x, 270), (box_x + 340, 300), (30, 30, 220), -1)
    return img


class _SimulatedCamera(Camera):
    def __init__(self) -> None:
        self._open = False

    def open(self, connection) -> None:
        self._open = True

    def close(self) -> None:
        self._open = False

    def capabilities(self) -> Capabilities:
        return Capabilities()

    def apply(self, profile, raw=None) -> ApplyReport:
        return ApplyReport(status={"exposure": SettingStatus.APPLIED})

    def read_back(self) -> dict:
        return {}

    def snapshot(self):
        return None

    def health(self) -> Health:
        return Health(self._open, 30.0, 0.0)

    def _box_x(self) -> int | None:  # overridden
        return None

    def frames(self) -> Iterator[Frame]:
        while self._open:
            yield Frame(scene(self._box_x()), time.monotonic())
            time.sleep(1 / 30)


class ScriptedCamera(_SimulatedCamera):
    """Empty 0-4 s, the box slides in 4-5.5 s, stays 5.5-14 s, then leaves; repeats every 20 s."""

    def __init__(self) -> None:
        super().__init__()
        self._t0 = time.monotonic()

    def _box_x(self) -> int | None:
        t = (time.monotonic() - self._t0) % 20
        return None if (t < 4 or t >= 14) else round(40 + 260 * min(1.0, (t - 4) / 1.5))


class ControlledCamera(_SimulatedCamera):
    """Shows an empty table or a box, as set: `camera.box = True` puts a box on the scale."""

    def __init__(self) -> None:
        super().__init__()
        self.box = False

    def _box_x(self) -> int | None:
        return 300 if self.box else None


def demo_job(name: str = "Caixa M — fita vermelha (demo)") -> JobBundle:
    data = {
        "format": 1,
        "job": {"id": "00000000-0000-4000-8000-0000000000d0", "name": name, "version": 1, "author": "demo", "created_at": "2026-10-14T00:00:00-03:00"},
        "camera_profile": "camera/profile.yaml",
        "trigger": {"mode": "image_presence", "presence_roi": [0.0, 0.0, 1.0, 1.0], "still_ms": 800, "min_area": 0.05},
        "quality": {"brightness": {"min": 0, "max": 255}, "sharpness_min_ratio": 0.5},
        "geometry": {"rois": {"all": {"relative_to": "frame", "rect": [0, 0, 1, 1]}}},
        "tools": [{"id": "code", "type": "code", "version": 1, "roi": "all", "reason_fail": "Código não lido"}],
        "ui": {"waiting": "Aguardando caixa"},
    }
    profile = CameraProfile.model_validate(
        {
            "resolution": [1920, 1080],
            "exposure": {"mode": "manual", "value_us": 8000},
            "gain": {"mode": "manual", "value": 0},
            "white_balance": {"mode": "manual", "kelvin": 4500},
            "focus": {"mode": "manual", "value": 30},
        }
    )
    return JobBundle(job=Job.model_validate(data), profile=profile)
