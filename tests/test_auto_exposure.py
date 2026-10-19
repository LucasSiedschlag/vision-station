"""*Auto uma vez* (FR-ACQ-11): the exposure is searched once, with the station paused, then kept as a fixed value."""

import math

import numpy as np
import pytest
import yaml

from test_station import Clock, FakeCamera, make_bundle
from vision_station.cameras import ApplyReport, Frame, SettingStatus
from vision_station.jobs import CameraProfile, dump_profile
from vision_station.jobs.camera_profile import AutoOnce
from vision_station.station import Acquisition
from vision_station.station.exposure import ExposureError, measure_exposure, saturated_percent


class LightCamera(FakeCamera):
    """A camera whose picture gets brighter with the exposure: a ramp of gray levels across the columns, times
    exposure / 10 000 µs. `step` makes it round the exposure to a factor-of-two ladder, like the C920."""

    def __init__(self, clock, ramp_max=255.0, step=False, right_only=False):
        super().__init__(clock)
        self.exposure_us = 10_000.0
        self.step = step
        columns = np.linspace(0, ramp_max, 200)
        if right_only:
            columns[:100] = 0  # the left half of the picture is dark whatever the exposure
        self.ramp = np.tile(columns, (100, 1))

    def apply(self, profile, raw=None):
        value = profile.exposure.value_us
        if value is not None:
            self.exposure_us = 2.0 ** round(math.log2(value)) if self.step else value
        self.applied.append(profile)
        return ApplyReport(status={"exposure": SettingStatus.APPLIED}, detail={"exposure": "x"})

    def read_back(self):
        return {"exposure": {"mode": "manual", "value_us": self.exposure_us}}

    def frames(self):
        while self.open_now:
            gray = np.clip(self.ramp * self.exposure_us / 10_000.0, 0, 255).astype(np.uint8)
            yield Frame(np.dstack([gray] * 3), self.clock())


def rig(**camera_options):
    clock = Clock()
    camera = LightCamera(clock, **camera_options)
    acq = Acquisition(camera, {}, clock=clock, settle_s=0.5)
    profile = make_bundle().profile
    acq.configure(profile)

    def pump():  # what the acquisition thread does, by hand
        clock.advance(0.1)
        acq.step()

    for _ in range(12):
        pump()
    return acq, camera, profile, pump


def test_the_search_stops_where_the_target_share_of_pixels_is_saturated():
    acq, camera, profile, pump = rig()
    profile = profile.model_copy(update={"exposure": profile.exposure.model_copy(update={"auto_once": AutoOnce(target_brightness=20)})})
    found = measure_exposure(acq, profile, pump=pump, clock=acq._clock)
    assert found.reached and found.limit == "" and abs(found.saturated_percent - 20) <= 1.0
    assert 100 <= found.value_us <= 100_000 and 3 <= len(found.steps) <= 10
    assert camera.exposure_us == pytest.approx(found.value_us, rel=1e-3)  # the live view is left on the result
    kept = acq.profile.exposure
    assert kept.mode == "manual" and kept.value_us == pytest.approx(found.value_us, abs=0.1)  # a fixed value, not "auto"


def test_a_camera_with_coarse_steps_gets_the_closest_step():
    acq, camera, profile, pump = rig(step=True)
    found = measure_exposure(acq, profile, pump=pump, clock=acq._clock)  # the default target: 10 %
    chosen = [m for m in found.steps if m.exposure_us == found.value_us][0]
    assert chosen.saturated_percent == found.saturated_percent
    assert found.value_us == camera.exposure_us  # the rung the camera really took, not the number that was asked for
    assert all(abs(m.saturated_percent - 10) >= abs(found.saturated_percent - 10) for m in found.steps)
    assert math.log2(camera.exposure_us) == round(math.log2(camera.exposure_us))  # a step of the ladder
    assert len(found.steps) <= 10  # a ladder of eleven rungs, not one measure for every number between two of them


def test_a_scene_that_never_reaches_the_target_ends_at_the_longest_exposure_and_says_so():
    acq, camera, profile, pump = rig(ramp_max=20.0)  # nothing is ever bright enough to saturate
    found = measure_exposure(acq, profile, pump=pump, clock=acq._clock)
    assert found.limit == "max" and not found.reached and found.value_us == 100_000 and found.saturated_percent == 0


def test_the_maximum_exposure_is_not_gone_over_by_a_camera_with_coarse_steps():
    acq, camera, profile, pump = rig(step=True, ramp_max=10.0)  # asked 100 000 µs, the ladder gives 131 072
    found = measure_exposure(acq, profile, pump=pump, clock=acq._clock)
    assert found.limit == "max" and found.value_us <= 100_000 and found.value_us == camera.exposure_us
    assert any(m.exposure_us > 100_000 for m in found.steps)  # the first measure went over, and was not chosen


def test_a_scene_that_is_over_the_target_even_at_the_shortest_exposure_ends_there():
    acq, camera, profile, pump = rig(ramp_max=255.0 * 1000)  # saturates at once
    found = measure_exposure(acq, profile, pump=pump, clock=acq._clock)
    assert found.limit == "min" and not found.reached and found.value_us == 100


def test_the_region_decides_what_is_measured():
    acq, camera, profile, pump = rig(right_only=True)
    on_dark_half = profile.model_copy(update={"exposure": profile.exposure.model_copy(update={"auto_once": AutoOnce(region=(0, 0, 0.5, 1))})})
    assert measure_exposure(acq, on_dark_half, pump=pump, clock=acq._clock).limit == "max"
    on_bright_half = profile.model_copy(update={"exposure": profile.exposure.model_copy(update={"auto_once": AutoOnce(region=(0.5, 0, 1, 1))})})
    assert measure_exposure(acq, on_bright_half, pump=pump, clock=acq._clock).reached


def test_a_camera_that_is_not_there_is_an_error_not_a_guess():
    clock = Clock()
    camera = LightCamera(clock)
    camera.fail_open = True
    acq = Acquisition(camera, {}, clock=clock)
    acq.configure(make_bundle().profile)

    def pump():
        clock.advance(0.5)
        acq.step()

    with pytest.raises(ExposureError, match="conectada"):
        measure_exposure(acq, make_bundle().profile, pump=pump, clock=clock, step_timeout_s=3)


def test_the_saturated_share_of_a_region():
    image = np.zeros((10, 10, 3), np.uint8)
    image[:, 5:] = 255
    assert saturated_percent(image, None) == 50.0
    assert saturated_percent(image, (0.5, 0, 1, 1)) == 100.0
    assert saturated_percent(image, (0, 0, 0.5, 1)) == 0.0


def test_the_parameters_are_written_only_when_set_and_must_make_sense():
    profile = make_bundle().profile
    assert "auto_once" not in dump_profile(profile)  # a job that does not use it still opens in an older version
    set_up = profile.model_copy(update={"exposure": profile.exposure.model_copy(update={"auto_once": AutoOnce(target_brightness=5, region=(0.2, 0.2, 0.8, 0.8))})})
    text = dump_profile(set_up)
    assert "auto_once" in text and CameraProfile.model_validate(yaml.safe_load(text)).exposure.auto_once.target_brightness == 5
    for bad in ({"region": [0.5, 0, 0.5, 1]}, {"target_brightness": 120}, {"max_exposure_us": 5}):
        with pytest.raises(ValueError):
            AutoOnce.model_validate(bad)
