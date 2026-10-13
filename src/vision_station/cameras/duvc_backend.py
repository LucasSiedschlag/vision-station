"""Windows backend for the UVC driver: duvc-ctl for the controls (TD-04).

Imports duvc-ctl only when used, so the package still loads on other systems.
"""

from collections.abc import Mapping
from typing import Any

from vision_station.cameras.base import CameraError
from vision_station.cameras.uvc import ControlError, ControlRange, Controls

# our control name -> duvc-ctl property name
PROPERTY = {
    "exposure": "exposure",
    "gain": "gain",
    "white_balance": "white_balance",
    "focus": "focus",
    "zoom": "zoom",
    "power_line_frequency": "power_line_frequency",
}


class DuvcControls:
    def __init__(self, controller: Any, duvc: Any):
        self._cam = controller
        self._duvc = duvc

    def range(self, name: str) -> ControlRange | None:
        try:
            info = self._cam.get_property_range(PROPERTY[name])
        except Exception:
            return None
        if not info:
            return None
        return ControlRange(min=info["min"], max=info["max"], step=max(1, info.get("step") or 1))

    def get(self, name: str) -> tuple[int, bool]:
        try:
            result = self._cam.core.get(self._prop(name))
            if not result.is_ok():
                raise ControlError(f"cannot read {name}: {result.error().description()}")
            setting = result.value()
            return int(setting.value), setting.mode == self._duvc.CamMode.Auto
        except ControlError:
            raise
        except Exception as exc:
            raise ControlError(f"cannot read {name}: {exc}") from exc

    def set(self, name: str, value: int, auto: bool) -> None:
        mode = self._duvc.CamMode.Auto if auto else self._duvc.CamMode.Manual
        try:
            result = self._cam.core.set(self._prop(name), self._duvc.PropSetting(int(value), mode))
            if not result.is_ok():
                raise ControlError(f"cannot set {name}: {result.error().description()}")
        except ControlError:
            raise
        except Exception as exc:
            raise ControlError(f"cannot set {name}: {exc}") from exc

    def close(self) -> None:
        self._cam.close()

    def _prop(self, name: str) -> Any:
        d = self._duvc
        return {
            "exposure": d.CamProp.Exposure,
            "focus": d.CamProp.Focus,
            "zoom": d.CamProp.Zoom,
            "gain": d.VidProp.Gain,
            "white_balance": d.VidProp.WhiteBalance,
            "power_line_frequency": d.VidProp.PowerLineFrequency,
        }[name]


def open_duvc_controls(connection: Mapping[str, Any]) -> tuple[Controls, int]:
    """Find the camera by device_path, device_name or device_index and open its controls.

    The returned index is the position in DirectShow's device list, which is what
    OpenCV's CAP_DSHOW backend expects. Prefer device_path in system.yaml: indexes
    change when USB devices are added or removed.
    """
    try:
        import duvc_ctl
    except ImportError as exc:
        raise CameraError("duvc-ctl is not installed (Windows only: uv sync --extra uvc)") from exc

    devices = duvc_ctl.list_devices()
    if not devices:
        raise CameraError("no cameras detected")

    if "device_path" in connection:
        matches = [i for i, d in enumerate(devices) if d.path == connection["device_path"]]
    elif "device_name" in connection:
        needle = str(connection["device_name"]).lower()
        matches = [i for i, d in enumerate(devices) if needle in d.name.lower()]
    elif "device_index" in connection:
        matches = [int(connection["device_index"])] if int(connection["device_index"]) < len(devices) else []
    else:
        raise CameraError("connection needs device_path, device_name or device_index")
    if not matches:
        raise CameraError(f"camera not found; available: {[d.name for d in devices]}")

    index = matches[0]
    try:
        controller = duvc_ctl.CameraController(device=devices[index])
    except Exception as exc:
        raise CameraError(f"cannot open camera controls: {exc}") from exc
    return DuvcControls(controller, duvc_ctl), index
