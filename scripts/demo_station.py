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
import time
from pathlib import Path

import cv2
import numpy as np

from vision_station.api import ApiDeps, AuthService, make_event_handler, serve
from vision_station.cameras import ApplyReport, Camera, Capabilities, Frame, Health, SettingStatus
from vision_station.jobs import CameraProfile, Job
from vision_station.records import ResultRecorder, ResultStore
from vision_station.results import InspectionResult, Outcome
from vision_station.station import Acquisition, StationController
from vision_station.store import JobBundle, JobStore


def scene(box_x: int | None) -> np.ndarray:
    img = np.zeros((540, 960, 3), np.uint8)
    img[:] = (70, 78, 84)
    cv2.rectangle(img, (0, 380), (960, 540), (50, 56, 62), -1)
    cv2.putText(img, "Vision Station demo", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (200, 200, 200), 2)
    if box_x is not None:
        cv2.rectangle(img, (box_x, 160), (box_x + 340, 400), (60, 90, 170), -1)
        cv2.rectangle(img, (box_x, 270), (box_x + 340, 300), (30, 30, 220), -1)
    return img


class ScriptedCamera(Camera):
    """Empty 0-4 s, the box slides in 4-5.5 s, stays 5.5-14 s, then leaves; repeats every 20 s."""

    def __init__(self) -> None:
        self._t0 = time.monotonic()
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

    def frames(self):
        while self._open:
            t = (time.monotonic() - self._t0) % 20
            box_x = None if (t < 4 or t >= 14) else round(40 + 260 * min(1.0, (t - 4) / 1.5))
            yield Frame(scene(box_x), time.monotonic())
            time.sleep(1 / 30)


def demo_job() -> JobBundle:
    data = {
        "format": 1,
        "job": {"id": "00000000-0000-4000-8000-0000000000d0", "name": "Caixa M — fita vermelha (demo)", "version": 1, "author": "demo", "created_at": "2026-10-14T00:00:00-03:00"},
        "camera_profile": "camera/profile.yaml",
        "trigger": {"mode": "image_presence", "presence_roi": [0.0, 0.0, 1.0, 1.0], "still_ms": 800, "min_area": 0.05},
        "quality": {"brightness": {"min": 0, "max": 255}, "sharpness_min_ratio": 0.5},
        "geometry": {"rois": {"all": {"relative_to": "frame", "rect": [0, 0, 1, 1]}}},
        "tools": [{"id": "code", "type": "code", "version": 1, "roi": "all", "reason_fail": "Código não lido"}],
        "ui": {"waiting": "Aguardando caixa"},
    }
    profile = CameraProfile.model_validate(
        {"resolution": [1920, 1080], "exposure": {"mode": "manual", "value_us": 8000}, "gain": {"mode": "manual", "value": 0},
         "white_balance": {"mode": "manual", "kelvin": 4500}, "focus": {"mode": "manual", "value": 30}}
    )
    return JobBundle(job=Job.model_validate(data), profile=profile)


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
