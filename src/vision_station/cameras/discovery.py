"""The USB cameras connected to this PC, and which models have been validated (VIA-0068, FR-ADM-8).

The commissioning wizard lists them so a person picks one instead of typing a driver and a device name. A model is
**validated** when it passed the bench trial (a long run, a disconnect and a restart, TD-04); nothing else is promised
about a camera that is not in the list. A model joins `VALIDATED_MODELS` only after that trial.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ValidatedModel:
    id: str  # also the name of its picture in the interface
    label: str
    name_contains: tuple[str, ...]  # lower case; a camera whose name contains one of them is this model


VALIDATED_MODELS: tuple[ValidatedModel, ...] = (ValidatedModel("c920", "Logitech C920", ("c920",)),)


def validated_model(name: str) -> ValidatedModel | None:
    lowered = name.lower()
    return next((m for m in VALIDATED_MODELS if any(part in lowered for part in m.name_contains)), None)


@dataclass(frozen=True)
class CameraFound:
    driver: str
    connection: dict[str, Any]  # what goes in the system configuration to open this one
    name: str
    model: str | None  # the id of the validated model, or None when the model is not validated


@dataclass(frozen=True)
class Discovery:
    available: bool  # false: this PC cannot list cameras (not Windows, or the driver library is missing)
    cameras: list[CameraFound] = field(default_factory=list)


def _duvc_devices() -> list[tuple[str, str]] | None:
    try:
        import duvc_ctl
    except ImportError:
        return None
    return [(d.name, d.path) for d in duvc_ctl.list_devices()]


def discover(list_devices: Callable[[], list[tuple[str, str]] | None] = _duvc_devices) -> Discovery:
    """`list_devices` gives (name, path) of each camera DirectShow knows, or None when it cannot be asked."""
    try:
        devices = list_devices()
    except Exception:  # a driver that does not answer must not break the wizard: it only cannot list
        return Discovery(available=False)
    if devices is None:
        return Discovery(available=False)
    names = [name for name, _ in devices]
    cameras = []
    for name, path in devices:
        # the name is what a person recognises and survives a change of USB port; two with the same name need the path
        connection = {"device_name": name} if names.count(name) == 1 else {"device_path": path}
        model = validated_model(name)
        cameras.append(CameraFound("uvc", connection, name, model.id if model else None))
    return Discovery(available=True, cameras=cameras)
