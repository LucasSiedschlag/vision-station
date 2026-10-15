"""The simulated station for the end-to-end tests (frontend/e2e) and for developing the interface without the bench:
no camera, and controls so a test decides what happens.

    uv run python scripts/e2e_station.py --port 8780

Besides the normal API it adds, on this machine only:
    POST /__e2e/box/{on|off}               put a box on the scale, or take it away
    POST /__e2e/outcome/{PASS|FAIL|ERROR}  what the next inspections return
    POST /__e2e/reset                      empty table, outcome PASS
Logins: supervisor / supervisor-pass and maintainer / maintainer-pass. Data goes to a temporary folder.
For `npm run dev` in frontend/, run it on port 8765.
"""

import argparse
import sys
import tempfile
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import cv2
import numpy as np

import uvicorn
from fastapi import HTTPException

from vision_station.api import ApiDeps, AuthService, create_app, make_event_handler
from vision_station.cameras import ApplyReport, Camera, Capabilities, Frame, Health, SettingStatus
from vision_station.jobs import CameraProfile, Job
from vision_station.records import ResultRecorder, ResultStore
from vision_station.results import InspectionResult, Outcome
from vision_station.station import Acquisition, StationController
from vision_station.store import JobBundle, JobStore


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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", type=int, default=8780)
    args = parser.parse_args()

    camera = ControlledCamera()
    outcome = {"next": Outcome.PASS}

    def inspect(bundle, frame) -> InspectionResult:
        if outcome["next"] is Outcome.PASS:
            return InspectionResult(Outcome.PASS, scores={"fita": 0.97}, duration_s=0.3)
        if outcome["next"] is Outcome.FAIL:
            return InspectionResult(Outcome.FAIL, "Fita ausente em 40% da emenda", scores={"fita": 0.58}, duration_s=0.3)
        return InspectionResult(Outcome.ERROR, "Imagem fora do padrão", duration_s=0.3)

    data = Path(tempfile.mkdtemp(prefix="vision-station-e2e-"))
    auth = AuthService(data / "system" / "users.json")
    auth.set_password("supervisor", "supervisor-pass")
    auth.set_password("maintainer", "maintainer-pass")
    results = ResultStore(data)
    acq = Acquisition(camera, {})
    controller = StationController(acq, inspect, absent_s=0.3)
    deps = ApiDeps(controller=controller, acquisition=acq, jobs=JobStore(data), results=results, auth=auth, inspect=inspect, recorder=ResultRecorder(results), backup_dir=data / "backups")
    controller._on_event = make_event_handler(deps)
    app = create_app(deps)

    @app.post("/__e2e/box/{state}")
    def box(state: str) -> dict[str, bool]:
        if state not in ("on", "off"):
            raise HTTPException(404)
        camera.box = state == "on"
        return {"box": camera.box}

    @app.post("/__e2e/outcome/{value}")
    def set_outcome(value: str) -> dict[str, str]:
        if value not in ("PASS", "FAIL", "ERROR"):
            raise HTTPException(404)
        outcome["next"] = Outcome(value)
        return {"outcome": value}

    @app.post("/__e2e/reset")
    def reset() -> dict[str, bool]:
        camera.box = False
        outcome["next"] = Outcome.PASS
        return {"ok": True}

    controller.start(demo_job())
    acq.start()
    threading.Thread(target=controller.run, daemon=True).start()
    try:
        uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")
    finally:
        controller.stop()
        acq.stop()
        results.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
