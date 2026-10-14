"""The station for the end-to-end tests (frontend/e2e): the demo, with controls so a test decides what happens.

    uv run python scripts/e2e_station.py --port 8780

Besides the normal API it adds, on this machine only:
    POST /__e2e/box/{on|off}               put a box on the scale, or take it away
    POST /__e2e/outcome/{PASS|FAIL|ERROR}  what the next inspections return
    POST /__e2e/reset                      empty table, outcome PASS
Logins: supervisor / supervisor-pass and maintainer / maintainer-pass. Data goes to a temporary folder.
"""

import argparse
import sys
import tempfile
import threading
from pathlib import Path

import uvicorn
from fastapi import HTTPException

from vision_station.api import ApiDeps, AuthService, create_app, make_event_handler
from vision_station.demo import ControlledCamera, demo_job
from vision_station.records import ResultRecorder, ResultStore
from vision_station.results import InspectionResult, Outcome
from vision_station.station import Acquisition, StationController
from vision_station.store import JobStore


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
