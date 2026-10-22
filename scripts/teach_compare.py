"""Teach the `compare` tool of a job from a folder of pictures of good parts.

    uv run python scripts/teach_compare.py JOB.vjob TOOL_ID PICTURES_FOLDER --out models/m.var

The pictures are frames of the station (the whole camera picture). For each one the fixtures of the job are located and the region of the tool is
cut, as in an inspection; the ones that cannot be used are listed with the reason. At least 3 are needed and 15 or more are advised. The file written
is the model, `models/<name>.var` of the job (`model: models/m.var` in the tool). The editor has no screen yet to add that file to a job (the upload of
the editor takes the model of a `detect` tool only); teaching from the station, which writes it into the job, is VIA-0126.
"""

import argparse
import sys
from pathlib import Path

import cv2

from vision_station.pipeline.teach import teach_tool
from vision_station.store.archive import unpack
from vision_station.store.bundle import bundle_from_files

EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("job", type=Path, help="a .vjob file")
    parser.add_argument("tool", help="the id of the compare tool in the job")
    parser.add_argument("pictures", type=Path, help="a folder of frames of good parts")
    parser.add_argument("--out", type=Path, required=True, help="the model file to write, e.g. m.var")
    args = parser.parse_args()
    try:
        # the job may not have the model yet (that is what this makes), so its tools are not checked for their files
        bundle = bundle_from_files(unpack(args.job.read_bytes(), "job").files, check_tools=False)
    except Exception as exc:  # a file that is not a job: say so, do not trace
        print(f"{args.job}: {exc}")
        return 1
    names = sorted(p for p in args.pictures.iterdir() if p.suffix.lower() in EXTENSIONS)
    pictures = []
    for path in names:
        image = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if image is None:
            print(f"skipped {path.name}: not a picture")
            continue
        pictures.append((path.name, image))
    try:
        taught = teach_tool(bundle, args.tool, pictures)
    except ValueError as exc:
        print(exc)
        return 1
    for skipped in taught.skipped:
        print(f"skipped {skipped.name}: {skipped.reason}")
    args.out.write_bytes(taught.data)
    advice = "" if taught.used >= 15 else " (15 or more are advised: with fewer, the floors hold the tolerance)"
    print(f"{args.out}: taught from {taught.used} of {len(pictures)} pictures, a region of {taught.size[0]}x{taught.size[1]}{advice}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
