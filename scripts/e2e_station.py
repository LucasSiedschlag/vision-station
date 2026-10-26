"""The simulated station for the end-to-end tests (frontend/e2e) and for developing the interface without the bench:
no camera, and controls so a test decides what happens.

    uv run python scripts/e2e_station.py --port 8780

Besides the normal API it adds, on this machine only:
    POST /__e2e/object/{on|off}            put an object at the station, or take it away
    POST /__e2e/outcome/{PASS|FAIL|ERROR}  what the next inspections return
    POST /__e2e/reset                      empty table, outcome PASS
    POST /__e2e/demo-job                   save the demo job, as the editor would (the wizard's last step)
Logins: supervisor / supervisor-pass and maintainer / maintainer-pass. Data goes to a temporary folder.
With `--fresh` the station is a clean installation instead: no passwords, no job, so the /setup wizard has all its
steps to do (the camera already sends images). Data goes to a new temporary folder on every start.
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
from vision_station.jobs import CameraProfile, Job, acquisition_block
from vision_station.records import ResultRecorder, ResultStore
from vision_station.core.results import InspectionResult, Mark, Outcome, ToolReport
from vision_station.station import Acquisition, StationController
from vision_station.store import JobBundle, JobStore
from vision_station.system import SystemConfig, SystemService
from vision_station.verification import EXPECTED_FILE, REFERENCE_IMAGE, activate, make_reference_files, verify_stored_job


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
        "format": 3,
        "job": {"id": "00000000-0000-4000-8000-0000000000d0", "name": name, "version": 1, "author": "demo", "created_at": "2026-10-14T00:00:00-03:00"},
        "acquisition": acquisition_block("image_presence", image_presence={"roi": [0.0, 0.0, 1.0, 1.0], "still_ms": 800, "min_area": 0.05}),
        "quality": {"brightness": {"min": 0, "max": 255}, "sharpness_min_ratio": 0.5},
        "geometry": {"rois": {"all": {"relative_to": "frame", "rect": [0, 0, 1, 1]}}},
        "tools": [{"id": "code", "type": "code", "version": 1, "roi": "all", "reason_fail": "Código não lido"}],
        "ui": {"waiting": "Aguardando peça"},
    }
    profile = CameraProfile.model_validate(
        {
            "resolution": [1920, 1080],
            "pixel_format": None,
            "exposure": {"mode": "manual", "value_us": 8000, "auto_once": {"target_brightness": 10, "max_exposure_us": 100000, "region": None}},
            "gain": {"mode": "manual", "value": 0},
            "white_balance": {"mode": "manual", "kelvin": 4500},
            "focus": {"mode": "manual", "value": 30},
            "zoom": None,
            "power_line_hz": 60,
            "low_light_compensation": False,
            "orientation": "normal",
        }
    )
    files = make_reference_files(scene(None))
    files["tests/images/ok.png"] = files[REFERENCE_IMAGE]
    files[EXPECTED_FILE] = b"cases:\n- {image: tests/images/ok.png, outcome: PASS}\n"
    return JobBundle(job=Job.model_validate(data), profile=profile, extra=files)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", type=int, default=8780)
    parser.add_argument("--fresh", action="store_true", help="a clean installation: no passwords and no job")
    args = parser.parse_args()

    camera = ControlledCamera()
    outcome = {"next": Outcome.PASS}

    def inspect(bundle, frame) -> InspectionResult:
        if outcome["next"] is Outcome.PASS:
            return InspectionResult(Outcome.PASS, scores={"tampa": 0.97}, duration_s=0.3)
        if outcome["next"] is Outcome.FAIL:
            # the cap, with the part of it that is not the colour drawn as a defect (VIA-0124)
            cap = ToolReport(
                "tampa", "color", 1, False, 0.58, {"fraction": 0.6}, {"fraction": "fraction"}, region=(0.4, 0.2, 0.7, 0.5),
                marks=(Mark("poly", "defect", ((0.45, 0.25), (0.65, 0.25), (0.55, 0.45))), Mark("text", "defect", ((0.45, 0.25),), text="fora da cor")),
            )
            return InspectionResult(Outcome.FAIL, "Tampa fora da cor em 40% da área", scores={"tampa": 0.58}, duration_s=0.3, tools=(cap,))
        return InspectionResult(Outcome.ERROR, "Imagem fora do padrão", duration_s=0.3)

    data = Path(tempfile.mkdtemp(prefix="vision-station-e2e-"))
    auth = AuthService(data / "system" / "users.json")
    if not args.fresh:
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

    @app.post("/__e2e/demo-job")
    def save_demo_job() -> dict[str, bool]:
        jobs.save(demo_job())
        return {"ok": True}

    if not args.fresh:
        ref = jobs.save(demo_job())  # in the store too, so the Jobs screen has something to list
        activate(jobs, ref, verify_stored_job(jobs, ref, inspect))
        controller.start(jobs.load(ref))
    acq.start()
    if not args.fresh:
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
