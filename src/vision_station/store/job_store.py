"""The job store on disk (architecture §4.4) and its backups (§4.3).

    <root>/system/active.yaml            which job version is active
    <root>/jobs/<job-id>/v<n>/           one folder per saved version: the files and manifest.json
    <root>/backups/                      local copies, if the caller chooses this folder

Rules: a saved version is never changed (new edits are new versions); every write goes to a
temporary place and is renamed into place, so a crash never leaves a half-written version;
an export or backup is read back and checked before it counts as done.
"""

import json
import os
import re
import shutil
import stat
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

import yaml

from vision_station import __version__
from vision_station.jobs import dump_job
from vision_station.store.archive import (
    MANIFEST,
    Archive,
    build_manifest,
    check_path,
    manifest_bytes,
    pack,
    refuse_secrets,
    sha256,
    unpack,
)
from vision_station.store.bundle import JobBundle, bundle_from_files
from vision_station.store.errors import FormatError, IntegrityError, StoreError

AUDIT_FILE = "audit.log"
ACTIVE_FILE = "active.yaml"
SYSTEM_FILE = "system.yaml"
BACKUP_GLOB = "backup_*.vbak"


@dataclass(frozen=True, order=True)
class JobRef:
    job_id: str
    version: int


@dataclass(frozen=True)
class ImportResult:
    ref: JobRef  # where it was stored
    original: JobRef  # what the file said it was
    status: Literal["added", "already_present", "renumbered"]


@dataclass(frozen=True)
class RestoreReport:
    imported: list[ImportResult]
    system_yaml: str | None  # the maintainer re-enters secrets and decides what to apply (UC-06)
    active: JobRef | None  # what was active when the backup was made; to be verified, not activated


def _now() -> datetime:
    return datetime.now().astimezone()


def _vjob_meta(job_id: str, version: int, created_at: str, app_version: str) -> dict[str, Any]:
    return {"job_id": job_id, "version": version, "created_at": created_at, "app_version": app_version}


class JobStore:
    def __init__(self, root: Path | str, clock: Callable[[], datetime] = _now):
        self.root = Path(root)
        self._clock = clock
        self.jobs_dir = self.root / "jobs"
        self.system_dir = self.root / "system"
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        self.system_dir.mkdir(parents=True, exist_ok=True)

    # --- reading -----------------------------------------------------------

    def job_ids(self) -> list[str]:
        return sorted(p.name for p in self.jobs_dir.iterdir() if p.is_dir() and not p.name.startswith("."))

    def versions(self, job_id: str) -> list[int]:
        folder = self.jobs_dir / job_id
        if not folder.is_dir():
            return []
        return sorted(int(p.name[1:]) for p in folder.iterdir() if p.is_dir() and p.name[1:].isdigit() and p.name[0] == "v")

    def latest(self, job_id: str) -> int | None:
        found = self.versions(job_id)
        return found[-1] if found else None

    def read_files(self, ref: JobRef) -> Archive:
        """The files of a saved version, checked against its manifest (catches damage on disk)."""
        folder = self._folder(ref)
        if not folder.is_dir():
            raise StoreError(f"no such job version: {ref.job_id} v{ref.version}")
        files = {p.relative_to(folder).as_posix(): p.read_bytes() for p in sorted(folder.rglob("*")) if p.is_file()}
        if MANIFEST not in files:
            raise IntegrityError(f"{MANIFEST} is missing in {ref.job_id} v{ref.version}")
        manifest = json.loads(files.pop(MANIFEST))
        listed = manifest.get("files", {})
        if set(listed) != set(files) or any(listed[n]["sha256"] != sha256(d) for n, d in files.items()):
            raise IntegrityError(f"stored version is damaged: {ref.job_id} v{ref.version}")
        return Archive(manifest=manifest, files=files)

    def load(self, ref: JobRef) -> JobBundle:
        return bundle_from_files(self.read_files(ref).files)

    # --- saving ------------------------------------------------------------

    def save(self, bundle: JobBundle) -> JobRef:
        """Store a new version of a job. A new job starts at 1; an edit must be latest + 1 and name its parent."""
        info = bundle.job.job
        job_id = str(info.id)
        latest = self.latest(job_id)
        if latest is None:
            if info.version != 1 or info.parent_version is not None:
                raise StoreError("a new job must be version 1 with no parent_version")
        elif info.version != latest + 1 or info.parent_version != latest:
            raise StoreError(f"the next version of this job is {latest + 1} with parent_version {latest}")
        files = bundle.files()
        bundle_from_files(files)  # the same checks an import gets
        return self._store(JobRef(job_id, info.version), files)

    def _store(self, ref: JobRef, files: Mapping[str, bytes], created_at: str | None = None, app_version: str | None = None) -> JobRef:
        refuse_secrets(files)
        final = self._folder(ref)
        if final.exists():
            raise StoreError(f"{ref.job_id} v{ref.version} is already saved and is never changed")
        final.parent.mkdir(parents=True, exist_ok=True)
        tmp = final.parent / f".tmp-{uuid.uuid4().hex}"
        meta = _vjob_meta(ref.job_id, ref.version, created_at or self._clock().isoformat(timespec="seconds"), app_version or __version__)
        manifest = build_manifest("job", files, meta)
        try:
            for name, data in {**files, MANIFEST: manifest_bytes(manifest)}.items():
                path = tmp / check_path(name)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
                os.chmod(path, stat.S_IREAD)
            os.rename(tmp, final)
        except BaseException:
            _remove_tree(tmp)
            raise
        return ref

    # --- export and import -------------------------------------------------

    def export_vjob(self, ref: JobRef) -> bytes:
        stored = self.read_files(ref)
        m = stored.manifest
        return pack("job", stored.files, _vjob_meta(ref.job_id, ref.version, m["created_at"], m["app_version"]))

    def write_vjob(self, ref: JobRef, dest_dir: Path | str, name: str | None = None) -> Path:
        """Write a `.vjob`, read the copy back and check it, and only then report it."""
        data = self.export_vjob(ref)
        return _write_verified(Path(dest_dir) / (name or f"{ref.job_id}_v{ref.version}.vjob"), data, lambda d: unpack(d, "job"))

    def _prepare_import(self, data: bytes) -> tuple[JobRef, dict[str, bytes], dict[str, Any]]:
        archive = unpack(data, "job")
        bundle = bundle_from_files(archive.files)
        refuse_secrets(archive.files)
        info = bundle.job.job
        return JobRef(str(info.id), info.version), archive.files, archive.manifest

    def import_vjob(self, data: bytes) -> ImportResult:
        """Add a job file as a new version. Existing versions are kept; nothing changes if the file is refused."""
        original, files, manifest = self._prepare_import(data)
        return self._import(original, files, manifest)

    def _import(self, original: JobRef, files: dict[str, bytes], manifest: dict[str, Any]) -> ImportResult:
        result = self._import_files(original, files, manifest)
        self.audit("import", job_id=original.job_id, original_version=original.version, stored_version=result.ref.version, status=result.status)
        return result

    def _import_files(self, original: JobRef, files: dict[str, bytes], manifest: dict[str, Any]) -> ImportResult:
        existing = self.versions(original.job_id)
        if original.version not in existing:
            ref = self._store(original, files, manifest.get("created_at"), manifest.get("app_version"))
            return ImportResult(ref, original, "added")
        if self.read_files(original).manifest["files"] == manifest["files"]:
            return ImportResult(original, original, "already_present")
        # the same id and version with different content: keep both, the incoming one becomes the next version
        bundle = bundle_from_files(files)
        new_version = existing[-1] + 1
        info = bundle.job.job.model_copy(update={"version": new_version, "parent_version": existing[-1]})
        renumbered = {**files, "job.yaml": dump_job(bundle.job.model_copy(update={"job": info})).encode("utf-8")}
        ref = self._store(JobRef(original.job_id, new_version), renumbered)
        return ImportResult(ref, original, "renumbered")

    # --- audit log ---------------------------------------------------------

    def audit(self, kind: str, **data: Any) -> None:
        """Append one line to the append-only audit log: who changed what and when (FR-LOG-5)."""
        line = json.dumps({"at": self._clock().isoformat(timespec="seconds"), "kind": kind, **data}, ensure_ascii=False, sort_keys=True)
        with open(self.system_dir / AUDIT_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    def read_audit(self) -> list[dict[str, Any]]:
        path = self.system_dir / AUDIT_FILE
        if not path.is_file():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    # --- the active job ----------------------------------------------------

    def set_active(self, ref: JobRef) -> None:
        """Record which version is active. The caller verifies the job first (FR-JOB-9); the store only records."""
        if ref.version not in self.versions(ref.job_id):
            raise StoreError(f"no such job version: {ref.job_id} v{ref.version}")
        text = yaml.safe_dump({"job_id": ref.job_id, "version": ref.version, "activated_at": self._clock().isoformat(timespec="seconds")})
        path = self.system_dir / ACTIVE_FILE
        tmp = path.with_name(f".{ACTIVE_FILE}.{uuid.uuid4().hex}")
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)

    def get_active(self) -> JobRef | None:
        path = self.system_dir / ACTIVE_FILE
        if not path.is_file():
            return None
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return JobRef(str(data["job_id"]), int(data["version"]))

    # --- backup ------------------------------------------------------------

    def make_backup(
        self,
        dest_dir: Path | str,
        include: Literal["all", "latest"] = "all",
        keep: int | None = 30,
        system_yaml: str | None = None,
    ) -> Path:
        """Pack every version of every job (or the latest of each), check the copy, then rotate old ones."""
        dest = Path(dest_dir)
        dest.mkdir(parents=True, exist_ok=True)
        files: dict[str, bytes] = {}
        listing: list[dict[str, Any]] = []
        for job_id in self.job_ids():
            versions = self.versions(job_id)
            for v in versions[-1:] if include == "latest" else versions:
                data = self.export_vjob(JobRef(job_id, v))
                path = f"jobs/{job_id}/v{v}.vjob"
                files[path] = data
                listing.append({"job_id": job_id, "version": v, "path": path, "sha256": sha256(data)})
        active = self.system_dir / ACTIVE_FILE
        if active.is_file():
            files[ACTIVE_FILE] = active.read_bytes()
        if system_yaml is not None:
            files[SYSTEM_FILE] = system_yaml.encode("utf-8")
            refuse_secrets({SYSTEM_FILE: files[SYSTEM_FILE]})
        now = self._clock()
        data = pack("backup", files, {"created_at": now.isoformat(timespec="seconds"), "app_version": __version__, "include": include, "jobs": listing})
        stem = f"backup_{now:%Y-%m-%d_%H%M}"
        target = dest / f"{stem}.vbak"
        n = 1
        while target.exists():
            target = dest / f"{stem}-{n}.vbak"
            n += 1
        path = _write_verified(target, data, _check_backup)
        if keep is not None:
            old_ones = sorted(dest.glob(BACKUP_GLOB), key=_backup_order)
            for old in old_ones[:-keep] if keep > 0 else old_ones:
                old.unlink()
        return path

    def restore_backup(self, data: bytes) -> RestoreReport:
        """Import every job version of a backup. The whole file is checked first: if anything is wrong, nothing is stored."""
        archive = unpack(data, "backup")
        _check_backup_contents(archive)
        plan = []
        for entry in archive.manifest["jobs"]:
            plan.append((entry, self._prepare_import(archive.files[entry["path"]])))
        stored: dict[JobRef, JobRef] = {}
        results: list[ImportResult] = []
        for _, (original, files, manifest) in sorted(plan, key=lambda p: (p[1][0].job_id, p[1][0].version)):
            result = self._import(original, files, manifest)
            results.append(result)
            stored[original] = result.ref
        active = None
        if ACTIVE_FILE in archive.files:
            a = yaml.safe_load(archive.files[ACTIVE_FILE])
            active = stored.get(JobRef(str(a["job_id"]), int(a["version"])))
        system = archive.files[SYSTEM_FILE].decode("utf-8") if SYSTEM_FILE in archive.files else None
        return RestoreReport(imported=results, system_yaml=system, active=active)

    # --- internals ---------------------------------------------------------

    def _folder(self, ref: JobRef) -> Path:
        check_path(ref.job_id)
        return self.jobs_dir / ref.job_id / f"v{ref.version}"


def _remove_tree(path: Path) -> None:
    """Delete a folder whose files were made read-only (Windows refuses to delete those)."""

    def writable_then_retry(func: Callable[[str], Any], name: str, _exc: BaseException) -> None:
        try:
            os.chmod(name, stat.S_IWRITE)
            func(name)
        except OSError:
            pass

    if path.exists():
        shutil.rmtree(path, onexc=writable_then_retry)


def _backup_order(path: Path) -> tuple[str, int]:
    """Oldest first: by the date in the name, then by the -n suffix used when two share a minute."""
    m = re.fullmatch(r"backup_(\d{4}-\d\d-\d\d_\d{4})(?:-(\d+))?\.vbak", path.name)
    return (m.group(1), int(m.group(2) or 0)) if m else (path.name, 0)


def _check_backup_contents(archive: Archive) -> None:
    jobs = archive.manifest.get("jobs")
    if not isinstance(jobs, list):
        raise FormatError("backup has no job list")
    for entry in jobs:
        data = archive.files.get(entry.get("path", ""))
        if data is None:
            raise IntegrityError(f"backup is missing {entry.get('path')}")
        if sha256(data) != entry.get("sha256"):
            raise IntegrityError(f"checksum does not match: {entry['path']}")
        unpack(data, "job")


def _check_backup(data: bytes) -> None:
    _check_backup_contents(unpack(data, "backup"))


def _write_verified(target: Path, data: bytes, check: Callable[[bytes], Any]) -> Path:
    """Write next to the target, read it back and check it, then rename into place."""
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(f".{target.name}.{uuid.uuid4().hex}.part")
    try:
        tmp.write_bytes(data)
        check(tmp.read_bytes())
        os.replace(tmp, target)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    return target
