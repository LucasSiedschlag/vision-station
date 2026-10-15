"""Prepare a data folder for the bench: the camera in system.yaml and a code-reading job, active.

    uv run python scripts/setup_bench.py --name C920 --exposure-us 33000      # once
    uv run python scripts/set_password.py maintainer                         # once
    uv run vision-station --data bench_data                                  # then http://127.0.0.1:8765

The job reads any bar code or 2D code in the whole picture (no reference image yet), so it is activated
with a recorded override. Real jobs are made on the screen (Jobs) and verified before they are activated.
"""

import argparse
import sys
from pathlib import Path

import yaml

from vision_station.jobs import CameraProfile, Job
from vision_station.pipeline import inspect_job
from vision_station.store import JobBundle, JobRef, JobStore
from vision_station.system import load_config, save_config
from vision_station.verification import activate, verify_job

DEFAULT_PROFILE = Path(__file__).parent.parent / "examples" / "c920-profile.yaml"
JOB_ID = "00000000-0000-4000-8000-000000000001"


def bench_job(profile: CameraProfile) -> JobBundle:
    data = {
        "format": 1,
        "job": {"id": JOB_ID, "name": "Leitura de código (bancada)", "version": 1, "author": "bancada", "created_at": "2026-10-15T00:00:00-03:00"},
        "camera_profile": "camera/profile.yaml",
        "trigger": {"mode": "image_presence", "presence_roi": [0.1, 0.1, 0.9, 0.9], "still_ms": 800, "min_area": 0.05},
        "quality": {"brightness": {"min": 15, "max": 245}, "sharpness_min_ratio": 0.5},
        "geometry": {"rois": {"all": {"relative_to": "frame", "rect": [0, 0, 1, 1]}}},
        "tools": [{"id": "codigo", "type": "code", "version": 1, "roi": "all", "reason_fail": "Código não lido"}],
        "ui": {"waiting": "Aguardando objeto com código"},
    }
    return JobBundle(job=Job.model_validate(data), profile=profile)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    camera = parser.add_mutually_exclusive_group(required=True)
    camera.add_argument("--name", help="camera name, e.g. C920 (uvc)")
    camera.add_argument("--path", help="camera device path (uvc)")
    camera.add_argument("--index", type=int, help="camera index (uvc)")
    camera.add_argument("--folder", help="a folder of images instead of a camera (file driver)")
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--exposure-us", type=float)
    parser.add_argument("--data", type=Path, default=Path("bench_data"))
    args = parser.parse_args()

    if args.folder:
        driver, connection = "file", {"path": args.folder, "loop": True, "fps": 10}
    else:
        driver = "uvc"
        connection = {"device_path": args.path} if args.path else {"device_name": args.name} if args.name else {"device_index": args.index}
    config = load_config(args.data)
    config = config.model_copy(update={"camera": config.camera.model_copy(update={"driver": driver, "connection": connection})})
    save_config(args.data, config)

    profile = CameraProfile.model_validate(yaml.safe_load(args.profile.read_text(encoding="utf-8")))
    if args.exposure_us is not None:
        profile = profile.model_copy(update={"exposure": profile.exposure.model_copy(update={"value_us": args.exposure_us})})
    store = JobStore(args.data)
    versions = store.versions(JOB_ID)
    ref = JobRef(JOB_ID, versions[-1]) if versions else store.save(bench_job(profile))
    report = verify_job(store.load(ref), inspect=inspect_job, parts="decision")
    activate(store, ref, report, override_reason="job de bancada, sem imagem de referência (scripts/setup_bench.py)")
    print(f"{args.data}: camera {driver} {connection}; job '{store.load(ref).job.job.name}' v{ref.version} active.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
