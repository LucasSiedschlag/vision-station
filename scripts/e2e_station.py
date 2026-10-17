"""The simulated station for the end-to-end tests (frontend/e2e) and for developing the interface without the bench:
no camera, and controls so a test decides what happens.

    uv run python scripts/e2e_station.py --port 8780

Besides the normal API it adds, on this machine only:
    POST /__e2e/object/{on|off}            put an object at the station, or take it away
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
from vision_station.core.results import InspectionResult, Outcome
from vision_station.station import Acquisition, StationController
from vision_station.store import JobBundle, JobStore
from vision_station.system import SystemConfig, SystemService


def scene(object_x: int | None) -> np.ndarray:
    """The station seen from above: a bench, and a part with a blue cap when `object_x` is given."""
    img = np.zeros((540, 960, 3), np.uint8)
    img[:] = (70, 78, 84)
    cv2.rectangle(img, (0, 380), (960, 540), (50, 56, 62), -1)
    cv2.putText(img, "Vision Station demo", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (200, 200, 200), 2)
    if object_x is not None:
        cv2.rectangle(img, (object_x, 160), (object_x + 340, 400), (150, 150, 150), -1)
        cv2.rectangle(img, (object_x + 110, 120), (object_x + 230, 170), (200, 90, 30), -1)
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

    def _object_x(self) -> int | None:  # overridden
        return None

    def frames(self) -> Iterator[Frame]:
        while self._open:
            yield Frame(scene(self._object_x()), time.monotonic())
            time.sleep(1 / 30)


class ControlledCamera(_SimulatedCamera):
    """Shows an empty bench or a part, as set: `camera.present = True` puts the part at the station."""

    def __init__(self) -> None:
        super().__init__()
        self.present = False

    def _object_x(self) -> int | None:
        return 300 if self.present else None


def demo_job(name: str = "Tampa azul — etiqueta de lote (demo)") -> JobBundle:
    data = {
        "format": 1,
        "job": {"id": "00000000-0000-4000-8000-0000000000d0", "name": name, "version": 1, "author": "demo", "created_at": "2026-10-14T00:00:00-03:00"},
        "camera_profile": "camera/profile.yaml",
        "trigger": {"mode": "image_presence", "presence_roi": [0.0, 0.0, 1.0, 1.0], "still_ms": 800, "min_area": 0.05},
        "quality": {"brightness": {"min": 0, "max": 255}, "sharpness_min_ratio": 0.5},
        "geometry": {"rois": {"all": {"relative_to": "frame", "rect": [0, 0, 1, 1]}}},
        "tools": [{"id": "code", "type": "code", "version": 1, "roi": "all", "reason_fail": "Código não lido"}],
        "ui": {"waiting": "Aguardando peça"},
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
            return InspectionResult(Outcome.PASS, scores={"tampa": 0.97}, duration_s=0.3)
        if outcome["next"] is Outcome.FAIL:
            return InspectionResult(Outcome.FAIL, "Tampa fora da cor em 40% da área", scores={"tampa": 0.58}, duration_s=0.3)
        return InspectionResult(Outcome.ERROR, "Imagem fora do padrão", duration_s=0.3)

    data = Path(tempfile.mkdtemp(prefix="vision-station-e2e-"))
    auth = AuthService(data / "system" / "users.json")
    auth.set_password("supervisor", "supervisor-pass")
    auth.set_password("maintainer", "maintainer-pass")
    results = ResultStore(data)
    acq = Acquisition(camera, {})
    controller = StationController(acq, inspect, absent_s=0.3)
    deps = ApiDeps(controller=controller, acquisition=acq, jobs=JobStore(data), results=results, auth=auth, inspect=inspect, recorder=ResultRecorder(results), backup_dir=data / "backups", system=SystemService(data, SystemConfig()))
    controller._on_event = make_event_handler(deps)
    app = create_app(deps)

    @app.post("/__e2e/object/{state}")
    def place(state: str) -> dict[str, bool]:
        if state not in ("on", "off"):
            raise HTTPException(404)
        camera.present = state == "on"
        return {"present": camera.present}

    @app.post("/__e2e/outcome/{value}")
    def set_outcome(value: str) -> dict[str, str]:
        if value not in ("PASS", "FAIL", "ERROR"):
            raise HTTPException(404)
        outcome["next"] = Outcome(value)
        return {"outcome": value}

    def speak(language: str) -> None:  # the station language, as Configurações › Estação would set it (TD-30)
        system = deps.system
        assert system is not None
        system._config = system.config.model_copy(update={"station": system.config.station.model_copy(update={"language": language})})

    @app.post("/__e2e/language/{value}")
    def set_language(value: str) -> dict[str, str]:
        if value not in ("pt-BR", "en"):
            raise HTTPException(404)
        speak(value)
        return {"language": value}

    @app.post("/__e2e/reset")
    def reset() -> dict[str, bool]:
        camera.present = False
        outcome["next"] = Outcome.PASS
        speak("pt-BR")
        return {"ok": True}

    jobs = deps.jobs
    ref = jobs.save(demo_job())  # in the store too, so the Jobs screen has something to list
    jobs.set_active(ref)
    controller.start(jobs.load(ref))
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
