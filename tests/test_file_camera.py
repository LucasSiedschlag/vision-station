from pathlib import Path

import cv2
import numpy as np
import pytest
import yaml

from vision_station.cameras import (
    CameraError,
    FileCamera,
    SettingStatus,
    create_camera,
)
from vision_station.cameras.base import SETTINGS
from vision_station.jobs import CameraProfile

FIXTURES = Path(__file__).parent / "fixtures"


class FakeClock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        self.now += 0.5
        return self.now


@pytest.fixture
def folder(tmp_path):
    for i, value in enumerate((10, 20, 30)):
        cv2.imwrite(str(tmp_path / f"{i}.png"), np.full((6, 8, 3), value, np.uint8))
    (tmp_path / "notes.txt").write_text("not an image")
    return tmp_path


@pytest.fixture
def profile():
    return CameraProfile.model_validate(yaml.safe_load((FIXTURES / "profile.yaml").read_text()))


def test_frames_come_in_name_order_and_end(folder):
    cam = FileCamera()
    cam.open({"path": folder})
    frames = list(cam.frames())
    assert [int(f.image[0, 0, 0]) for f in frames] == [10, 20, 30]
    assert frames[0].image.shape == (6, 8, 3)


def test_loop_repeats_until_closed(folder):
    cam = FileCamera(loop=True)
    cam.open({"path": folder})
    values = []
    for frame in cam.frames():
        values.append(int(frame.image[0, 0, 0]))
        if len(values) == 7:
            cam.close()
    assert values == [10, 20, 30, 10, 20, 30, 10]


def test_timestamps_increase(folder):
    cam = FileCamera(clock=FakeClock())
    cam.open({"path": folder})
    stamps = [f.timestamp for f in cam.frames()]
    assert stamps == sorted(stamps) and len(set(stamps)) == 3


def test_apply_reports_every_setting_as_not_supported(folder, profile):
    cam = FileCamera()
    cam.open({"path": folder})
    report = cam.apply(profile)
    assert set(report.status) == set(SETTINGS)
    assert all(s is SettingStatus.NOT_SUPPORTED for s in report.status.values())
    assert not report.ok
    assert cam.read_back() == {}


def test_snapshot_and_capabilities(folder):
    cam = FileCamera()
    cam.open({"path": folder})
    assert cam.capabilities().has_snapshot
    assert int(cam.snapshot().image[0, 0, 0]) == 10


def test_health_before_and_after_frames(folder):
    cam = FileCamera(clock=FakeClock())
    assert cam.health().connected is False
    cam.open({"path": folder})
    health = cam.health()
    assert health.connected and health.last_frame_age_s is None
    list(cam.frames())
    health = cam.health()
    assert health.fps == pytest.approx(2.0)  # fake clock: one tick = 0.5 s
    assert health.last_frame_age_s == pytest.approx(0.5)
    cam.close()
    assert cam.health().connected is False


def test_errors(tmp_path, folder):
    cam = FileCamera()
    with pytest.raises(CameraError, match="not open"):
        cam.snapshot()
    with pytest.raises(CameraError, match="not found"):
        cam.open({"path": tmp_path / "missing"})
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(CameraError, match="no images"):
        cam.open({"path": empty})
    (folder / "3.png").write_bytes(b"broken")
    cam.open({"path": folder})
    with pytest.raises(CameraError, match="cannot read"):
        list(cam.frames())


def test_driver_is_chosen_by_name(folder):
    with create_camera("file") as cam:
        cam.open({"path": folder})
        assert len(list(cam.frames())) == 3
    with pytest.raises(CameraError, match="unknown camera driver"):
        create_camera("nope")
