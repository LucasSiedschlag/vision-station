"""What build is running (TD-15 version stamping): the version, the git commit and the build date.

An installed program carries `build_info.json` next to its files (written by packaging/build_windows.ps1);
a checkout reports its version and "dev".
"""

import json
import sys
from functools import cache
from pathlib import Path

from vision_station import __version__


def bundle_dir() -> Path | None:
    """The folder of the installed (PyInstaller) program's own files, or None when run from a checkout."""
    base = getattr(sys, "_MEIPASS", None)
    return Path(base) if getattr(sys, "frozen", False) and base else None


@cache
def build_info() -> dict[str, str]:
    info = {"version": __version__, "commit": "dev", "built_at": ""}
    folder = bundle_dir()
    if folder and (folder / "build_info.json").is_file():
        try:
            info.update(json.loads((folder / "build_info.json").read_text(encoding="utf-8")))
        except (OSError, ValueError):
            pass
    return info


def describe() -> str:
    i = build_info()
    return " · ".join(p for p in (i["version"], i["commit"], i["built_at"]) if p)
