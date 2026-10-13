"""The camera interface every driver implements (architecture §5.1).

Inspection and job code use only this module, never a specific camera
(NFR-POR-4).
"""

from abc import ABC, abstractmethod
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

import numpy as np

from vision_station.jobs import CameraProfile

# Names used in reports and capabilities: the fields of CameraProfile
SETTINGS = tuple(CameraProfile.model_fields)


class CameraError(Exception):
    """The camera could not be opened, or stopped delivering frames."""


class SettingStatus(StrEnum):
    APPLIED = "applied"
    NOT_SUPPORTED = "not_supported"
    REJECTED = "rejected"


@dataclass(frozen=True)
class Frame:
    image: np.ndarray  # BGR, uint8
    timestamp: float  # monotonic seconds, taken when the frame was captured


@dataclass(frozen=True)
class Capabilities:
    """Which settings this unit has and which of them can be read back."""

    settings: frozenset[str] = frozenset()
    readable: frozenset[str] = frozenset()
    has_snapshot: bool = False


@dataclass(frozen=True)
class ApplyReport:
    """Outcome per setting. A setting is never silently skipped (FR-JOB-11)."""

    status: Mapping[str, SettingStatus]
    detail: Mapping[str, str] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return all(s is SettingStatus.APPLIED for s in self.status.values())

    def failed(self) -> dict[str, SettingStatus]:
        return {k: s for k, s in self.status.items() if s is not SettingStatus.APPLIED}


@dataclass(frozen=True)
class Health:
    connected: bool
    fps: float
    last_frame_age_s: float | None  # None until the first frame


class Camera(ABC):
    @abstractmethod
    def open(self, connection: Mapping[str, Any]) -> None:
        """Connect. `connection` comes from the system config, never from a job."""

    @abstractmethod
    def close(self) -> None: ...

    @abstractmethod
    def capabilities(self) -> Capabilities: ...

    @abstractmethod
    def apply(self, profile: CameraProfile, raw: Mapping[str, bytes] | None = None) -> ApplyReport:
        """Write the settings in the order the camera needs, one report entry per setting."""

    @abstractmethod
    def read_back(self) -> dict[str, Any]:
        """Current values of the readable settings, by CameraProfile field name."""

    @abstractmethod
    def frames(self) -> Iterator[Frame]:
        """Continuous frames for the acquisition thread."""

    @abstractmethod
    def snapshot(self) -> Frame | None:
        """One full-quality still, or None if the camera does not offer it."""

    @abstractmethod
    def health(self) -> Health: ...

    def __enter__(self) -> "Camera":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
