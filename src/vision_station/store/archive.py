"""The ZIP container shared by job files (`.vjob`) and backup files (`.vbak`).

Layout (architecture §4.2): `manifest.json` plus the files it lists, each with its
SHA-256 and size. Paths are relative, use `/` and are UTF-8 (NFR-POR-3). Packing is
deterministic (sorted entries, fixed timestamps), so the same content gives the same bytes.
"""

import hashlib
import io
import json
import zipfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

import yaml

from vision_station.store.errors import FormatError, IntegrityError, StoreError

FORMAT = 1
MANIFEST = "manifest.json"
MAX_FILE_BYTES = 256 * 1024 * 1024
MAX_TOTAL_BYTES = 1024 * 1024 * 1024
_ZIP_TIME = (1980, 1, 1, 0, 0, 0)
_SECRET_WORDS = ("password", "passwd", "secret", "token", "credential", "apikey", "api_key")

# format -> function that upgrades (manifest, files) one format up. Newer software adds an
# entry here for each format it replaces, and upgrades on import, never in place (NFR-MAI-1).
MIGRATORS: dict[int, Callable[[dict[str, Any], dict[str, bytes]], tuple[dict[str, Any], dict[str, bytes]]]] = {}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def check_path(name: str) -> str:
    """Refuse paths that could leave the folder they are unpacked into."""
    parts = name.split("/")
    bad = (
        not name
        or name.startswith("/")
        or "\\" in name
        or ":" in name
        or "\x00" in name
        or len(name) > 240
        or any(p in ("", ".", "..") for p in parts)
    )
    if bad:
        raise FormatError(f"unsafe path in file: {name!r}")
    return name


def _secret_keys(data: Any, where: str) -> list[str]:
    found: list[str] = []
    if isinstance(data, dict):
        for key, value in data.items():
            if any(w in str(key).lower() for w in _SECRET_WORDS):
                found.append(f"{where}.{key}")
            found += _secret_keys(value, f"{where}.{key}")
    elif isinstance(data, list):
        for i, item in enumerate(data):
            found += _secret_keys(item, f"{where}[{i}]")
    return found


def refuse_secrets(files: Mapping[str, bytes]) -> None:
    """Jobs and backups never carry passwords or tokens (NFR-SEC-1, TD-16). YAML files are scanned by key."""
    for name, data in files.items():
        if not name.endswith((".yaml", ".yml")):
            continue
        try:
            parsed = yaml.safe_load(data)
        except yaml.YAMLError as exc:
            raise FormatError(f"{name} is not valid YAML: {exc}") from exc
        found = _secret_keys(parsed, name)
        if found:
            raise StoreError(f"refusing to write secrets: {', '.join(found)}")


def build_manifest(kind: str, files: Mapping[str, bytes], meta: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "format": FORMAT,
        "kind": kind,
        **meta,
        "files": {n: {"sha256": sha256(d), "size": len(d)} for n, d in sorted(files.items())},
    }


def content_hash(manifest: Mapping[str, Any]) -> str:
    """One hash for a saved version's files: of each file's SHA-256 in its manifest, by name. It changes with any
    file and with nothing else (not the dates or the program version of the manifest); results carry it (TD-22)."""
    listed = {name: entry["sha256"] for name, entry in sorted(manifest["files"].items())}
    return sha256(json.dumps(listed, sort_keys=True).encode("utf-8"))


def manifest_bytes(manifest: Mapping[str, Any]) -> bytes:
    return json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False).encode("utf-8")


def pack(kind: str, files: Mapping[str, bytes], meta: Mapping[str, Any]) -> bytes:
    for name in files:
        check_path(name)
        if name == MANIFEST:
            raise StoreError(f"{MANIFEST} is written by the packer, not passed in")
    manifest = build_manifest(kind, files, meta)
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in [(MANIFEST, manifest_bytes(manifest)), *sorted(files.items())]:
            info = zipfile.ZipInfo(name, _ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, data)
    return out.getvalue()


def kind_of(data: bytes) -> str:
    """'job' or 'backup', read from the manifest without checking the rest."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            return str(json.loads(zf.read(MANIFEST).decode("utf-8"))["kind"])
    except (zipfile.BadZipFile, KeyError, ValueError, TypeError) as exc:
        raise FormatError("not a valid Vision Station file") from exc


@dataclass(frozen=True)
class Archive:
    manifest: dict[str, Any]
    files: dict[str, bytes]  # without the manifest


def unpack(data: bytes, kind: str) -> Archive:
    """Read and check an archive. Raises FormatError or IntegrityError and changes nothing."""
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise FormatError("not a valid Vision Station file (damaged or not a ZIP)") from exc
    with zf:
        infos = [i for i in zf.infolist() if not i.is_dir()]
        names = [i.filename for i in infos]
        if len(set(names)) != len(names):
            raise IntegrityError("file lists the same entry twice")
        for name in names:
            check_path(name)
        if sum(i.file_size for i in infos) > MAX_TOTAL_BYTES or any(i.file_size > MAX_FILE_BYTES for i in infos):
            raise FormatError("file is larger than the allowed size")
        if MANIFEST not in names:
            raise FormatError(f"{MANIFEST} is missing")
        try:
            manifest = json.loads(zf.read(MANIFEST).decode("utf-8"))
            fmt = manifest["format"]
        except (ValueError, KeyError, TypeError) as exc:
            raise FormatError(f"{MANIFEST} is not readable") from exc
        files = {n: zf.read(n) for n in names if n != MANIFEST}

    if manifest.get("kind") != kind:
        raise FormatError(f"this is a '{manifest.get('kind')}' file, not a '{kind}' file")
    if not isinstance(fmt, int) or fmt < 1:
        raise FormatError(f"unknown format {fmt!r}")
    # every format lists its files and checksums in `files`, so damage is caught before any upgrade
    if fmt > FORMAT:
        raise FormatError(f"file format {fmt} is newer than this software supports ({FORMAT}); update Vision Station")
    listed = manifest.get("files")
    if not isinstance(listed, dict):
        raise FormatError(f"{MANIFEST} has no file list")
    if set(listed) != set(files):
        missing = sorted(set(listed) - set(files))
        extra = sorted(set(files) - set(listed))
        raise IntegrityError(f"file list does not match the content (missing {missing}, unlisted {extra})")
    for name, data_ in files.items():
        entry = listed[name]
        if entry.get("sha256") != sha256(data_) or entry.get("size") != len(data_):
            raise IntegrityError(f"checksum does not match: {name}")
    while fmt < FORMAT:
        if fmt not in MIGRATORS:
            raise FormatError(f"file format {fmt} is no longer supported")
        manifest, files = MIGRATORS[fmt](manifest, files)
        fmt = manifest["format"]
    return Archive(manifest=manifest, files=files)
