"""Read codes with the C920 through the code tool (Windows, camera plugged in).

    uv run python scripts/read_codes.py --name C920
    uv run python scripts/read_codes.py --name C920 --seconds 10 --expect LOTE-2026-10

Opens the camera with examples/c920-profile.yaml, runs the code tool on every frame for
the given time and prints each distinct code with how often it was read. Saves the last
frame with the codes outlined as codes_last.png.
"""

import argparse
import sys
import time
from collections import Counter
from pathlib import Path

import cv2
import numpy as np
import yaml

from vision_station.cameras import create_camera
from vision_station.jobs import CameraProfile
from vision_station.tools import run_tool

DEFAULT_PROFILE = Path(__file__).parent.parent / "examples" / "c920-profile.yaml"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--name", help="part of the camera name")
    parser.add_argument("--path", help="device path")
    parser.add_argument("--index", type=int)
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--seconds", type=float, default=5)
    parser.add_argument("--expect", help="accept only codes with exactly this text")
    parser.add_argument("--formats", nargs="*", help="e.g. QRCode Code128 DataMatrix (default: all)")
    args = parser.parse_args()

    connection = {"device_path": args.path} if args.path else {"device_name": args.name} if args.name else {"device_index": args.index}
    if args.path is None and args.name is None and args.index is None:
        parser.error("give --name, --path or --index")

    profile = CameraProfile.model_validate(yaml.safe_load(args.profile.read_text(encoding="utf-8")))
    params = {k: v for k, v in {"expect": args.expect, "formats": args.formats}.items() if v}

    cam = create_camera("uvc")
    cam.open(connection)
    seen: Counter[tuple[str, str]] = Counter()
    frames = passed = 0
    last = None
    try:
        report = cam.apply(profile)
        if not report.ok:
            print("camera settings not applied:", report.failed())
        started = time.monotonic()
        for frame in cam.frames():
            result = run_tool("code", 1, frame.image, params)
            frames += 1
            passed += result.passed
            for c in result.details["codes"]:
                seen[(c["format"], c["text"])] += 1
            last = (frame.image, result)
            if time.monotonic() - started > args.seconds:
                break
        elapsed = time.monotonic() - started
    finally:
        cam.close()

    print(f"{frames} frames in {elapsed:.1f} s ({frames / elapsed:.1f} per s), tool passed in {passed}")
    for (fmt, text), n in seen.most_common():
        print(f"  {fmt:<12} {text!r:<30} read in {n}/{frames} frames")
    if not seen:
        print("  no code read")
    if last is not None:
        image, result = last
        for c in result.details["codes"]:
            cv2.polylines(image, [np.array(c["position"], np.int32)], True, (0, 200, 0) if c["accepted"] else (0, 0, 255), 3)
        cv2.imwrite("codes_last.png", image)
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
