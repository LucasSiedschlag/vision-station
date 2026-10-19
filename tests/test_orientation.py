"""The image orientation of the camera profile (FR-ACQ-10, TD-32): applied once, where frames enter."""

import numpy as np
import pytest
import yaml

from test_station import Clock, FakeCamera, empty_scene, make_bundle, scene_with_object
from test_verification import make_bundle as verified_bundle
from vision_station.cameras.base import SETTINGS
from vision_station.cameras.orientation import orient
from vision_station.jobs import CameraProfile, PROGRAM_SIDE, dump_profile
from vision_station.station import Acquisition
from vision_station.store import JobBundle
from vision_station.store.bundle import bundle_from_files as load_bundle
from vision_station.verification import run_reference_set
from vision_station.pipeline import inspect_job


def asymmetric() -> np.ndarray:
    image = np.zeros((6, 8, 3), np.uint8)
    image[0, 0] = (255, 0, 0)  # top left
    image[0, 7] = (0, 255, 0)  # top right
    return image


def test_the_three_turns_move_the_corners_and_never_change_the_size():
    image = asymmetric()
    assert orient(image, "normal") is image
    mirrored, flipped, turned = (orient(image, o) for o in ("mirror", "flip", "rotate180"))
    assert (mirrored[0, 0] == image[0, 7]).all() and (mirrored[0, 7] == image[0, 0]).all()
    assert (flipped[5, 0] == image[0, 0]).all() and (flipped[5, 7] == image[0, 7]).all()
    assert (turned[5, 7] == image[0, 0]).all() and (turned[5, 0] == image[0, 7]).all()
    assert all(o.shape == image.shape for o in (mirrored, flipped, turned))


def acquisition_with(orientation: str):
    clock = Clock()
    camera = FakeCamera(clock, scene=asymmetric())
    acq = Acquisition(camera, {}, clock=clock)
    acq.configure(make_bundle().profile.model_copy(update={"orientation": orientation}))
    clock.advance(1)
    acq.step()
    return acq, clock


@pytest.mark.parametrize("orientation", ["normal", "mirror", "flip", "rotate180"])
def test_every_frame_the_station_uses_comes_out_oriented(orientation):
    acq, clock = acquisition_with(orientation)
    clock.advance(1)
    acq.step()
    assert (acq.latest().image == orient(asymmetric(), orientation)).all()


def test_changing_the_orientation_applies_to_the_frames_after_it():
    acq, clock = acquisition_with("normal")
    clock.advance(1)
    acq.step()
    assert (acq.latest().image == asymmetric()).all()
    acq.configure(acq.profile.model_copy(update={"orientation": "mirror"}))
    clock.advance(1)
    acq.step()
    clock.advance(1)
    acq.step()
    assert (acq.latest().image == orient(asymmetric(), "mirror")).all()


def test_it_is_not_a_camera_setting():
    assert PROGRAM_SIDE == ("orientation",)
    assert "orientation" not in SETTINGS and "exposure" in SETTINGS  # a report lists what the camera is given


def test_a_normal_orientation_is_not_written_so_an_older_version_still_opens_the_job():
    profile = make_bundle().profile
    assert "orientation" not in dump_profile(profile)
    assert "orientation: mirror" in dump_profile(profile.model_copy(update={"orientation": "mirror"}))
    bundle = make_bundle()
    files = bundle.files()
    assert b"orientation" not in files["camera/profile.yaml"]
    turned = JobBundle(bundle.job, bundle.profile.model_copy(update={"orientation": "rotate180"}), bundle.extra)
    assert load_bundle(turned.files()).profile.orientation == "rotate180"
    assert load_bundle(files).profile.orientation == "normal"  # a profile without the key means normal
    with pytest.raises(ValueError):
        CameraProfile.model_validate({**yaml.safe_load(dump_profile(profile)), "orientation": "sideways"})


def test_stored_pictures_are_not_turned_again():
    """The reference and the samples were taken oriented: running the job on them must not depend on the
    orientation of the profile."""
    plain = verified_bundle()
    turned = JobBundle(plain.job, plain.profile.model_copy(update={"orientation": "mirror"}), plain.extra)
    ran = lambda b: [(r.image, r.outcome, r.ok) for r in run_reference_set(b, inspect_job)]
    assert ran(plain) == ran(turned)
