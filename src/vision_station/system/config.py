"""System configuration: what describes this installation, not a product (architecture §4.5).

    <data root>/system/system.yaml

Camera driver and connection, recording limits, backups, the station's name and shifts, and the network.
Never a password: a camera that needs one names an entry of the OS secret store (`keyring_entry`), and
the file is refused if any key looks like a secret (NFR-SEC-1). Written atomically. A missing file means
the defaults; a damaged one is an error that names the problem, never silently replaced.
"""

import os
import re
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Annotated, Any, Literal, Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from vision_station.cameras import DRIVERS
from vision_station.records import RecordingConfig
from vision_station.store.archive import refuse_secrets

SYSTEM_DIR = "system"
SYSTEM_FILE = "system.yaml"
# sections whose change takes effect only after the program restarts (the screen says so)
RESTART_SECTIONS = ("camera", "network")
_HHMM = re.compile(r"([01]\d|2[0-3]):[0-5]\d")


class ConfigError(Exception):
    """system.yaml is damaged or not valid; the message says where."""


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class StationSettings(_Strict):
    name: Annotated[str, Field(min_length=1, max_length=80)] = "Estação de visão"
    shift_starts: Annotated[list[str], Field(min_length=1, max_length=6)] = ["00:00"]  # counters start again at each
    idle_logout_min: Annotated[int, Field(ge=1, le=240)] = 10
    fail_sound: bool = False
    result_min_s: Annotated[float, Field(ge=0, le=30)] = 2.0  # a verdict stays on screen at least this long (VIA-0049)
    # the language of the operator screen and the default of the other screens (TD-30); applies at once
    language: Literal["pt-BR", "en"] = "pt-BR"
    # when the operator screen draws the regions on the image, and whether the operator may toggle it (FR-UI-9)
    markings: Literal["always", "on_fail", "never"] = "on_fail"
    operator_markings: bool = True

    @field_validator("shift_starts")
    @classmethod
    def _times(cls, starts: list[str]) -> list[str]:
        bad = [s for s in starts if not _HHMM.fullmatch(s)]
        if bad:
            raise ValueError(f"shift starts must be HH:MM: {bad}")
        return sorted(set(starts))


class CameraSettings(_Strict):
    driver: str = "uvc"
    # uvc: device_name, device_path or device_index; file: path; hikvision: host, port, user
    connection: dict[str, Any] = {}
    keyring_entry: str | None = None  # where the camera's password is kept in the OS secret store
    # frames dropped after the settings are written: the C920 sends overexposed frames first (VIA-0045)
    settle_ms: Annotated[int, Field(ge=0, le=5000)] = 500
    # only uniform (black) frames for this long = camera lost: an unplugged C920 sends them with no error (VIA-0050)
    dead_after_s: Annotated[float, Field(ge=0, le=60)] = 2.0

    @field_validator("driver")
    @classmethod
    def _known(cls, driver: str) -> str:
        if driver not in DRIVERS:
            raise ValueError(f"unknown camera driver '{driver}' (available: {sorted(DRIVERS)})")
        return driver


class RecordingSettings(_Strict):
    pass_sample_every: Annotated[int, Field(ge=1)] = 1  # keep the image of 1 PASS in N; FAIL and ERROR always
    unsampled_pass_hours: Annotated[float, Field(gt=0)] | None = None
    retention_days: Annotated[float, Field(gt=0)] | None = None  # None: keep everything
    min_free_gb: Annotated[float, Field(gt=0)] | None = None

    def to_recording_config(self) -> RecordingConfig:
        return RecordingConfig(
            pass_sample_every=self.pass_sample_every,
            unsampled_pass_hours=self.unsampled_pass_hours,
            retention_days=self.retention_days,
            min_free_bytes=round(self.min_free_gb * 1024**3) if self.min_free_gb else None,
        )


class BackupSettings(_Strict):
    folder: str | None = None  # a network share or a USB drive; None: backups only to <data root>/backups
    every_hours: Annotated[float, Field(gt=0)] | None = 24.0  # None: only when asked
    keep: Annotated[int, Field(ge=1, le=1000)] = 30
    include: Literal["all", "latest"] = "all"


class NetworkSettings(_Strict):
    host: str = "127.0.0.1"  # anything else opens the API to the network (NFR-SEC-3)
    port: Annotated[int, Field(ge=1, le=65535)] = 8765
    allowed_hosts: list[str] = []  # extra Host names accepted when open to the network
    # web pages of other programs allowed to call the API from a browser (CORS), e.g. http://localhost:8800
    allowed_origins: list[str] = []

    @field_validator("allowed_origins")
    @classmethod
    def _origins(cls, origins: list[str]) -> list[str]:
        bad = [o for o in origins if not re.fullmatch(r"https?://[^/\s]+", o)]
        if bad:
            raise ValueError(f"origins must look like http://host:port, without a path: {bad}")
        return origins

    @property
    def local_only(self) -> bool:
        return self.host in ("127.0.0.1", "localhost", "::1")


class SystemConfig(_Strict):
    format: Literal[1] = 1
    station: StationSettings = StationSettings()
    camera: CameraSettings = CameraSettings()
    recording: RecordingSettings = RecordingSettings()
    backup: BackupSettings = BackupSettings()
    network: NetworkSettings = NetworkSettings()

    @model_validator(mode="after")
    def _no_secrets(self) -> Self:
        try:
            refuse_secrets({SYSTEM_FILE: dump_config(self).encode("utf-8")})
        except Exception as exc:
            raise ValueError(f"system.yaml must not carry secrets ({exc}); name an OS secret store entry in camera.keyring_entry") from exc
        return self


def dump_config(config: SystemConfig) -> str:
    data = config.model_dump(mode="json")
    if data["station"]["language"] == "pt-BR":
        # written only when not Portuguese, so a backup of a station in Portuguese still restores on version 0.1
        del data["station"]["language"]
    # the same for the markings: written only when changed
    for key, default in (("markings", "on_fail"), ("operator_markings", True)):
        if data["station"][key] == default:
            del data["station"][key]
    return yaml.safe_dump(data, sort_keys=False, allow_unicode=True)


def config_path(root: Path | str) -> Path:
    return Path(root) / SYSTEM_DIR / SYSTEM_FILE


def parse_config(text: str) -> SystemConfig:
    try:
        return SystemConfig.model_validate(yaml.safe_load(text) or {})
    except (ValidationError, yaml.YAMLError) as exc:
        raise ConfigError(f"{SYSTEM_FILE} is not valid: {exc}") from exc


def load_config(root: Path | str) -> SystemConfig:
    path = config_path(root)
    if not path.is_file():
        return SystemConfig()
    return parse_config(path.read_text(encoding="utf-8"))


def save_config(root: Path | str, config: SystemConfig) -> Path:
    path = config_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{SYSTEM_FILE}.{uuid.uuid4().hex}")
    tmp.write_text(dump_config(config), encoding="utf-8")
    os.replace(tmp, path)
    return path


def changed_sections(old: SystemConfig, new: SystemConfig) -> list[str]:
    a, b = old.model_dump(), new.model_dump()
    return [k for k in b if a.get(k) != b[k]]


def shift_start(config: SystemConfig, now: datetime) -> datetime:
    """When the current shift started: the latest configured start not after `now` (yesterday's last one
    before the first start of the day)."""
    starts = [now.replace(hour=int(s[:2]), minute=int(s[3:]), second=0, microsecond=0) for s in config.station.shift_starts]
    past = [s for s in starts if s <= now]
    return max(past) if past else max(starts) - timedelta(days=1)


def default_data_root() -> Path:
    """`VISION_STATION_DATA` if set; on Windows C:\\ProgramData\\VisionSystem (TD-15); elsewhere
    ~/.local/share/vision-station."""
    configured = os.environ.get("VISION_STATION_DATA")
    if configured:
        return Path(configured)
    if sys.platform == "win32":
        return Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / "VisionSystem"
    return Path.home() / ".local" / "share" / "vision-station"
