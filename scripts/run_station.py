"""Run the station controller with the C920 and a stand-in inspection (Windows, camera plugged in).

    uv run python scripts/run_station.py --name C920
    uv run python scripts/run_station.py --name C920 --exposure-us 33000 --still-ms 800

With the scene empty, press Enter once to take it as the empty scene (or just leave it empty at start). Put an
object in the area: the station waits until it is still, takes one picture, runs the stand-in
inspection (PASS if a code is read in the picture, FAIL if not) and shows the result. Remove the object to
re-arm. Every state change and result is printed; pictures of the results go to station_out/.
Stop with Ctrl+C. The real pipeline (VIA-0008) replaces the stand-in.
"""

import argparse
import sys
import threading
import time
from pathlib import Path

import cv2
import yaml

from vision_station.cameras import create_camera
from vision_station.jobs import CameraProfile, Job
from vision_station.results import InspectionResult, Outcome
from vision_station.station import Acquisition, StationController, StationEvent
from vision_station.store import JobBundle
from vision_station.system import SystemConfig
from vision_station.tools import run_tool

DEFAULT_PROFILE = Path(__file__).parent.parent / "examples" / "c920-profile.yaml"


def build_job(profile: CameraProfile, still_ms: int, min_area: float) -> JobBundle:
    data = {
        "format": 1,
        "job": {"id": "00000000-0000-4000-8000-000000000001", "name": "Teste da estação", "version": 1, "author": "bancada", "created_at": "2026-10-14T00:00:00-03:00"},
        "camera_profile": "camera/profile.yaml",
        "trigger": {"mode": "image_presence", "presence_roi": [0.1, 0.1, 0.9, 0.9], "still_ms": still_ms, "min_area": min_area},
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
    parser.add_argument("--still-ms", type=int, default=800)
    parser.add_argument("--min-area", type=float, default=0.05, help="fraction of the area that must change to count as an object")
    parser.add_argument("--settle-ms", type=int, default=SystemConfig().camera.settle_ms, help="frames dropped after the settings are written (camera.settle_ms)")
    args = parser.parse_args()
    connection = {"device_path": args.path} if args.path else {"device_name": args.name} if args.name else {"device_index": args.index}
    if args.path is None and args.name is None and args.index is None:
        parser.error("give --name, --path or --index")

    profile = CameraProfile.model_validate(yaml.safe_load(args.profile.read_text(encoding="utf-8")))
    if args.exposure_us is not None:
        profile = profile.model_copy(update={"exposure": profile.exposure.model_copy(update={"value_us": args.exposure_us})})
    out = Path("station_out")
    out.mkdir(exist_ok=True)
    started = time.monotonic()
    count = 0

    def inspect(bundle: JobBundle, frame) -> InspectionResult:
        result = run_tool("code", 1, frame.image, {})
        texts = result.values["texts"]
        return InspectionResult(Outcome.PASS if result.passed else Outcome.FAIL, f"lido: {texts}" if result.passed else "código não lido", details=result.details)

    def show(event: StationEvent) -> None:
        nonlocal count
        stamp = f"{time.monotonic() - started:7.1f}s"
        if event.kind == "state":
            print(f"{stamp}  {event.previous} -> {event.state}  {event.message}")
        else:
            count += 1
            print(f"{stamp}  RESULTADO {event.result.outcome}: {event.result.reason}  ({event.result.duration_s * 1000:.0f} ms)")
            if event.frame is not None:
                cv2.imwrite(str(out / f"{count:03d}_{event.result.outcome}.png"), event.frame.image)

    acq = Acquisition(create_camera("uvc"), connection, settle_s=args.settle_ms / 1000)
    controller = StationController(acq, inspect, on_event=show)
    controller.start(build_job(profile, args.still_ms, args.min_area))
    acq.start()
    runner = threading.Thread(target=controller.run, daemon=True)
    runner.start()
    print("estação rodando; Enter = tomar a cena atual como vazia, Ctrl+C = sair")
    try:
        while True:
            input()
            controller.reset_background()
            print("cena atual tomada como vazia")
    except (KeyboardInterrupt, EOFError):
        pass
    finally:
        controller.stop()
        acq.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
