from collections.abc import Callable

from vision_station.cameras.base import (
    ApplyReport,
    Camera,
    CameraError,
    Capabilities,
    Frame,
    Health,
    SettingStatus,
)
from vision_station.cameras.file import FileCamera

# Driver name (as written in the system config) -> factory (FR-ACQ-3)
DRIVERS: dict[str, Callable[[], Camera]] = {"file": FileCamera}


def create_camera(driver: str) -> Camera:
    try:
        return DRIVERS[driver]()
    except KeyError:
        raise CameraError(f"unknown camera driver '{driver}', available: {sorted(DRIVERS)}") from None


__all__ = [
    "ApplyReport",
    "Camera",
    "CameraError",
    "Capabilities",
    "DRIVERS",
    "FileCamera",
    "Frame",
    "Health",
    "SettingStatus",
    "create_camera",
]
