"""The station with its API, on the C920, with a stand-in inspection (Windows, camera plugged in).

    uv run python scripts/set_password.py supervisor      # once
    uv run python scripts/run_api.py --name C920 --exposure-us 33000

Then open http://127.0.0.1:8765/docs for the endpoints, or try:
    curl http://127.0.0.1:8765/state
    curl -X POST http://127.0.0.1:8765/trigger
    (websocat or a browser page on ws://127.0.0.1:8765/live for the live view)
Data goes to bench_data/ (jobs, results, images, dataset). Listens on this machine only.
"""

import argparse
import sys
import threading
from pathlib import Path

import yaml

from vision_station.api import ApiDeps, AuthService, make_event_handler, serve
from vision_station.cameras import create_camera
from vision_station.jobs import CameraProfile, Job
from vision_station.records import ResultRecorder, ResultStore
from vision_station.results import InspectionResult, Outcome
from vision_station.station import Acquisition, StationController
from vision_station.store import JobBundle, JobStore
from vision_station.tools import run_tool

DEFAULT_PROFILE = Path(__file__).parent.parent / "examples" / "c920-profile.yaml"


def stand_in_inspection(bundle: JobBundle, frame) -> InspectionResult:
    r = run_tool("code", 1, frame.image, {})
    return InspectionResult(Outcome.PASS if r.passed else Outcome.FAIL, f"lido: {r.values['texts']}" if r.passed else "código não lido", scores={"code": r.score}, details=r.details)


def demo_job(profile: CameraProfile) -> JobBundle:
    data = {
        "format": 1,
        "job": {"id": "00000000-0000-4000-8000-000000000001", "name": "Teste da estação", "version": 1, "author": "bancada", "created_at": "2026-10-14T00:00:00-03:00"},
        "camera_profile": "camera/profile.yaml",
        "trigger": {"mode": "image_presence", "presence_roi": [0.1, 0.1, 0.9, 0.9], "still_ms": 800, "min_area": 0.05},
        "quality": {"brightness": {"min": 0, "max": 255}, "sharpness_min_ratio": 0.5},
        "geometry": {"rois": {"all": {"relative_to": "frame", "rect": [0, 0, 1, 1]}}},
        "tools": [{"id": "code", "type": "code", "version": 1, "roi": "all", "reason_fail": "Código não lido"}],
    }
    return JobBundle(job=Job.model_validate(data), profile=profile)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--name")
    parser.add_argument("--path")
    parser.add_argument("--index", type=int)
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--exposure-us", type=float)
    parser.add_argument("--data", type=Path, default=Path("bench_data"))
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    connection = {"device_path": args.path} if args.path else {"device_name": args.name} if args.name else {"device_index": args.index}
    if args.path is None and args.name is None and args.index is None:
        parser.error("give --name, --path or --index")

    profile = CameraProfile.model_validate(yaml.safe_load(args.profile.read_text(encoding="utf-8")))
    if args.exposure_us is not None:
        profile = profile.model_copy(update={"exposure": profile.exposure.model_copy(update={"value_us": args.exposure_us})})

    jobs, results = JobStore(args.data), ResultStore(args.data)
    auth = AuthService(args.data / "system" / "users.json")
    if not (auth.has_password("supervisor") or auth.has_password("maintainer")):
        print("No password set yet: only the operator endpoints will work. Run scripts/set_password.py.")
    acq = Acquisition(create_camera("uvc"), connection)
    controller = StationController(acq, stand_in_inspection)
    deps = ApiDeps(controller=controller, acquisition=acq, jobs=jobs, results=results, auth=auth, inspect=stand_in_inspection, recorder=ResultRecorder(results), backup_dir=args.data / "backups")
    controller._on_event = make_event_handler(deps)

    bundle = demo_job(profile)
    ref = jobs.save(bundle) if not jobs.versions(str(bundle.job.job.id)) else jobs.versions(str(bundle.job.job.id))
    controller.start(bundle)
    acq.start()
    threading.Thread(target=controller.run, daemon=True).start()
    try:
        serve(deps, port=args.port)
    finally:
        controller.stop()
        acq.stop()
        results.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
