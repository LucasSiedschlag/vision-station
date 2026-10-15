"""The running system's configuration: change it, apply what can be applied now, and the scheduled chores.

`SystemService` keeps the configuration the program started with apart from the saved one: camera and
network changes take effect after a restart, and `restart_pending` says which. Recording limits, backups
and the station's settings apply at once through `on_apply`.

`Maintenance.tick()` runs the hourly housekeeping of the results and the automatic backup (FR-JOB-10);
the program calls it about once a minute.
"""

import logging
import shutil
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

from vision_station.cameras import CameraError, create_camera
from vision_station.records import ResultStore
from vision_station.store import JobStore
from vision_station.system.config import RESTART_SECTIONS, CameraSettings, SystemConfig, changed_sections, dump_config, save_config

log = logging.getLogger(__name__)


class SystemService:
    def __init__(self, root: Path | str, config: SystemConfig, on_apply: Callable[[SystemConfig], None] = lambda c: None):
        self.root = Path(root)
        self.started_with = config
        self._config = config
        self.on_apply = on_apply
        self._lock = threading.Lock()

    @property
    def config(self) -> SystemConfig:
        return self._config

    @property
    def restart_pending(self) -> list[str]:
        return [s for s in changed_sections(self.started_with, self._config) if s in RESTART_SECTIONS]

    def backup_dir(self) -> Path:
        folder = self._config.backup.folder
        return Path(folder) if folder else self.root / "backups"

    def update(self, new: SystemConfig) -> list[str]:
        """Save `new` and apply what applies now. Returns the sections that changed."""
        with self._lock:
            changed = changed_sections(self._config, new)
            if changed:
                save_config(self.root, new)
                self._config = new
                self.on_apply(new)
            return changed


@dataclass
class CheckReport:
    ok: bool
    message: str  # Portuguese, for the screen
    width: int | None = None
    height: int | None = None
    free_gb: float | None = None


def check_folder(path: str) -> CheckReport:
    """Write, read back and delete a small file; report the free space."""
    folder = Path(path)
    try:
        folder.mkdir(parents=True, exist_ok=True)
        probe = folder / f".vision-station-test-{uuid.uuid4().hex}"
        data = uuid.uuid4().bytes
        probe.write_bytes(data)
        try:
            same = probe.read_bytes() == data
        finally:
            probe.unlink(missing_ok=True)
        free = shutil.disk_usage(folder).free / 1024**3
    except OSError as exc:
        return CheckReport(False, f"Não foi possível gravar na pasta: {exc.strerror or exc}")
    if not same:
        return CheckReport(False, "A pasta devolveu um conteúdo diferente do gravado")
    return CheckReport(True, f"Pasta gravável, {free:.1f} GB livres", free_gb=round(free, 1))


def check_camera(settings: CameraSettings, timeout_s: float = 5.0) -> CheckReport:
    """Open a camera, wait for one frame, close it. Not for the camera the station is using (a USB camera
    can be opened by one program at a time): the caller reports that one's health instead."""
    try:
        camera = create_camera(settings.driver)
        camera.open(settings.connection)
    except (CameraError, KeyError, OSError, ValueError) as exc:
        return CheckReport(False, f"A câmera não abriu: {exc}")
    try:
        deadline = time.monotonic() + timeout_s
        for frame in camera.frames():
            image = frame.image
            if isinstance(image, np.ndarray) and image.size:
                h, w = image.shape[:2]
                return CheckReport(True, f"Câmera respondeu: imagem de {w}×{h}", width=w, height=h)
            if time.monotonic() > deadline:
                break
        return CheckReport(False, "A câmera abriu, mas não mandou imagem")
    except (CameraError, OSError) as exc:
        return CheckReport(False, f"A câmera parou de responder: {exc}")
    finally:
        camera.close()


class Maintenance:
    def __init__(self, system: SystemService, jobs: JobStore, results: ResultStore, clock: Callable[[], datetime] = lambda: datetime.now().astimezone()):
        self.system = system
        self.jobs = jobs
        self.results = results
        self._clock = clock
        self._last_housekeeping: datetime | None = None
        self._retry_backup_at: datetime | None = None
        self.last_backup_error: str | None = None

    def tick(self) -> None:
        now = self._clock()
        if self._last_housekeeping is None or (now - self._last_housekeeping).total_seconds() >= 3600:
            self._last_housekeeping = now
            try:
                self.results.housekeeping()
            except Exception:
                log.exception("housekeeping failed")
        self._backup_if_due(now)

    def _newest_backup(self, folder: Path) -> datetime | None:
        try:
            files = list(folder.glob("backup_*.vbak"))
        except OSError:
            return None
        if not files:
            return None
        return datetime.fromtimestamp(max(f.stat().st_mtime for f in files)).astimezone()

    def _backup_if_due(self, now: datetime) -> None:
        settings = self.system.config.backup
        if settings.every_hours is None or not self.jobs.job_ids():
            return
        if self._retry_backup_at is not None and now < self._retry_backup_at:
            return  # a failed backup is retried every 15 min, not every tick
        folder = self.system.backup_dir()
        newest = self._newest_backup(folder)
        if newest is not None and (now - newest).total_seconds() < settings.every_hours * 3600:
            return
        try:
            path = self.jobs.make_backup(folder, include=settings.include, keep=settings.keep, system_yaml=dump_config(self.system.config))
        except Exception as exc:
            self.last_backup_error = str(exc)
            self._retry_backup_at = now + timedelta(minutes=15)
            log.exception("automatic backup failed")
            self.jobs.audit("backup_failed", automatic=True, folder=str(folder), error=str(exc))
            return
        self.last_backup_error = None
        self._retry_backup_at = None
        self.jobs.audit("backup", automatic=True, file=path.name, folder=str(folder))
