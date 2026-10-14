"""The station and its screens with a simulated camera, to try the interface without the bench (any computer).

    uv run python scripts/demo_station.py
    open http://127.0.0.1:8765/

A scripted scene repeats every 20 s (empty, a box with red tape sliding in, still, then taken away) and a stand-in
inspection alternates APROVADO and REPROVADO, so every state of the operator screen shows up. Logins:
supervisor / supervisor-pass and maintainer / maintainer-pass. Data goes to a temporary folder.
"""

import argparse
import itertools
import sys
import tempfile
import threading
from pathlib import Path

from vision_station.api import ApiDeps, AuthService, make_event_handler, serve
from vision_station.demo import ScriptedCamera, demo_job
from vision_station.records import ResultRecorder, ResultStore
from vision_station.results import InspectionResult, Outcome
from vision_station.station import Acquisition, StationController
from vision_station.store import JobStore


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    counter = itertools.count()

    def inspect(bundle, frame) -> InspectionResult:
        if next(counter) % 2 == 0:
            return InspectionResult(Outcome.PASS, scores={"fita": 0.97}, duration_s=0.31)
        return InspectionResult(Outcome.FAIL, "Fita ausente em 40% da emenda", scores={"fita": 0.58}, duration_s=0.29)

    data = Path(tempfile.mkdtemp(prefix="vision-station-demo-"))
    auth = AuthService(data / "system" / "users.json")
    auth.set_password("supervisor", "supervisor-pass")
    auth.set_password("maintainer", "maintainer-pass")
    results = ResultStore(data)
    acq = Acquisition(ScriptedCamera(), {})
    controller = StationController(acq, inspect)
    deps = ApiDeps(controller=controller, acquisition=acq, jobs=JobStore(data), results=results, auth=auth, inspect=inspect, recorder=ResultRecorder(results), backup_dir=data / "backups")
    controller._on_event = make_event_handler(deps)
    controller.start(demo_job())
    acq.start()
    threading.Thread(target=controller.run, daemon=True).start()
    print(f"Demo running: http://127.0.0.1:{args.port}/  (data in {data})")
    try:
        serve(deps, port=args.port)
    finally:
        controller.stop()
        acq.stop()
        results.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
