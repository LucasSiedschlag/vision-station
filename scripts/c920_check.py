"""Bench check of the C920 driver (test 1 of docs/technical-decisions.md section 7).

Run on the Windows PC with the camera plugged in:

    uv sync --extra uvc
    uv run python scripts/c920_check.py --list
    uv run python scripts/c920_check.py --name C920 --repeat 20

For each repetition it opens the camera, applies the profile, reads it back, grabs
frames to measure fps and checks that nothing was rejected. Saves the last frame as
c920_last.png. Exit code 1 if any repetition had a setting that did not apply.
"""

import argparse
import sys
import time
from pathlib import Path

import cv2
import yaml

from vision_station.cameras import SettingStatus, create_camera
from vision_station.jobs import CameraProfile

DEFAULT_PROFILE = Path(__file__).parent.parent / "examples" / "c920-profile.yaml"


def list_devices() -> None:
    import duvc_ctl

    for i, device in enumerate(duvc_ctl.list_devices()):
        print(f"{i}: {device.name}\n   {device.path}")


def run_once(connection: dict, profile: CameraProfile, frames: int, save: Path | None) -> bool:
    cam = create_camera("uvc")
    cam.open(connection)
    try:
        report = cam.apply(profile)
        for name, status in report.status.items():
            note = f"  ({report.detail[name]})" if name in report.detail else ""
            print(f"  {name:<24} {status.value}{note}")
        print("  read back:", cam.read_back())
        started = time.monotonic()
        last = None
        for count, frame in enumerate(cam.frames(), 1):
            last = frame
            if count >= frames:
                break
        elapsed = time.monotonic() - started
        print(f"  {frames} frames in {elapsed:.2f} s = {frames / elapsed:.1f} fps, shape {last.image.shape}")
        if save and last is not None:
            cv2.imwrite(str(save), last.image)
        bad = {k: v for k, v in report.status.items() if v is SettingStatus.REJECTED}
        return not bad
    finally:
        cam.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--list", action="store_true", help="list cameras and exit")
    parser.add_argument("--name", help="part of the camera name, e.g. C920")
    parser.add_argument("--path", help="device path, as printed by --list")
    parser.add_argument("--index", type=int, help="position in the DirectShow list")
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--repeat", type=int, default=1, help="open/apply/close this many times")
    parser.add_argument("--frames", type=int, default=60)
    args = parser.parse_args()

    if args.list:
        list_devices()
        return 0

    if args.path:
        connection = {"device_path": args.path}
    elif args.name:
        connection = {"device_name": args.name}
    elif args.index is not None:
        connection = {"device_index": args.index}
    else:
        parser.error("give --name, --path or --index (see --list)")

    profile = CameraProfile.model_validate(yaml.safe_load(args.profile.read_text(encoding="utf-8")))
    failures = 0
    for n in range(1, args.repeat + 1):
        print(f"run {n}/{args.repeat}")
        if not run_once(connection, profile, args.frames, Path("c920_last.png")):
            failures += 1
    print(f"\n{args.repeat - failures}/{args.repeat} runs with every setting applied")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
