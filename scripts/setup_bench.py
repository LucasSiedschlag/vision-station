"""Prepare a data folder for the bench: the camera in system.yaml and a code-reading job, active.

    uv run python scripts/setup_bench.py --name C920 --reference reference.png --exposure-us 33000      # once
    uv run python scripts/setup_bench.py --folder path/to/pictures                                      # no camera
    uv run python scripts/set_password.py maintainer                                                    # once
    uv run vision-station --data bench_data                                  # then http://127.0.0.1:8765

The job reads any bar code or 2D code in the whole picture. Like every job it needs a reference image (a view of
the bench with a readable code) and a reference set, or the station would not run it (FR-JOB-9, design rule 4,
VIA-0090): the reference image is also the one case of the set, expected PASS. With `--folder` the first picture of the
folder is the reference unless `--reference` says another; with a camera `--reference` is required. Real jobs are made on
the screen (Jobs) and verified before they are activated.
"""

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

import cv2
import numpy as np
import yaml

from vision_station.jobs import CameraProfile, Job, acquisition_block
from vision_station.pipeline import inspect_job
from vision_station.store import JobBundle, JobRef, JobStore
from vision_station.system import load_config, save_config
from vision_station.verification import EXPECTED_FILE, REFERENCE_IMAGE, VerificationFailed, activate, make_reference_files, verify_job

DEFAULT_PROFILE = Path(__file__).parent.parent / "examples" / "c920-profile.yaml"
JOB_ID = "00000000-0000-4000-8000-000000000001"


def bench_job(profile: CameraProfile, reference: np.ndarray) -> JobBundle:
    data = {
        "format": 3,
        "job": {"id": JOB_ID, "name": "Leitura de código (bancada)", "version": 1, "author": "bancada", "created_at": "2026-10-15T00:00:00-03:00"},
        "acquisition": acquisition_block("image_presence", image_presence={"roi": [0.1, 0.1, 0.9, 0.9], "still_ms": 800, "min_area": 0.05}),
        "quality": {"brightness": {"min": 15, "max": 245}, "sharpness_min_ratio": 0.5},
        "geometry": {"rois": {"all": {"relative_to": "frame", "rect": [0, 0, 1, 1]}}},
        "tools": [{"id": "codigo", "type": "code", "version": 1, "roi": "all", "reason_fail": "Código não lido"}],
        "ui": {"waiting": "Aguardando objeto com código"},
    }
    files = make_reference_files(reference)
    files["tests/images/ok.png"] = files[REFERENCE_IMAGE]
    files[EXPECTED_FILE] = b"cases:\n- {image: tests/images/ok.png, outcome: PASS}\n"
    return JobBundle(job=Job.model_validate(data), profile=profile, extra=files)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    camera = parser.add_mutually_exclusive_group(required=True)
    camera.add_argument("--name", help="camera name, e.g. C920 (uvc)")
    camera.add_argument("--path", help="camera device path (uvc)")
    camera.add_argument("--index", type=int, help="camera index (uvc)")
    camera.add_argument("--folder", help="a folder of images instead of a camera (file driver)")
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--exposure-us", type=float)
    parser.add_argument("--data", type=Path, default=Path("bench_data"))
    parser.add_argument("--reference", type=Path, help="a picture of the bench with a readable code (with --folder: the first picture of the folder)")
    args = parser.parse_args(argv)
    reference_path = args.reference
    if reference_path is None and args.folder:
        pictures = sorted(p for p in Path(args.folder).iterdir() if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".bmp"))
        reference_path = pictures[0] if pictures else None
    if reference_path is None:
        parser.error("--reference is required: a picture of the bench with a readable code (a job needs a reference image, FR-JOB-9)")
    reference = cv2.imread(str(reference_path))
    if reference is None:
        parser.error(f"cannot read the reference picture {reference_path}")

    if args.folder:
        driver, connection = "file", {"path": str(Path(args.folder).resolve()), "loop": True, "fps": 10}
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
    if versions:
        ref = JobRef(JOB_ID, versions[-1])
        if REFERENCE_IMAGE not in store.load(ref).extra:
            parser.error(f"{args.data} has the bench job of an older run, without a reference image: use another --data folder, or delete this one")
    else:
        ref = store.save(bench_job(profile, reference))
    try:
        activate(store, ref, verify_job(store.load(ref), inspect=inspect_job, parts="decision"))
    except VerificationFailed as exc:
        print(f"the bench job was not activated: {exc}", file=sys.stderr)
        for check in exc.report.failures():
            print(f"  - {check.message}", file=sys.stderr)
        return 1
    print(f"{args.data}: camera {driver} {connection}; job '{store.load(ref).job.job.name}' v{ref.version} active.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
