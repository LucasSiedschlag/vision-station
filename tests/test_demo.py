import time

from vision_station.demo import ControlledCamera, ScriptedCamera, demo_job, scene
from vision_station.tools import check_job_tools


def test_the_demo_job_is_a_valid_job_the_software_can_run():
    bundle = demo_job()
    check_job_tools(bundle.job)
    assert bundle.job.ui.waiting == "Aguardando caixa" and bundle.job.trigger.mode == "image_presence"


def test_the_scene_has_a_box_only_when_asked():
    empty, boxed = scene(None), scene(300)
    assert empty.shape == boxed.shape == (540, 960, 3)
    assert (empty != boxed).any()
    assert (scene(300)[250:260, 400:410] == (60, 90, 170)).all()  # the cardboard colour inside the box


def test_a_controlled_camera_shows_what_it_is_told_and_only_while_open():
    camera = ControlledCamera()
    camera.open({})
    frames = camera.frames()
    first = next(frames)
    camera.box = True
    deadline = time.monotonic() + 2
    changed = False
    while time.monotonic() < deadline and not changed:
        changed = (next(frames).image != first.image).any()
    assert changed
    camera.close()
    assert list(camera.frames()) == []  # a closed camera delivers nothing


def test_the_scripted_camera_runs_by_the_clock():
    camera = ScriptedCamera()
    assert camera._box_x() is None  # the first seconds are an empty table
    camera._t0 -= 8  # eight seconds later the box is in place
    assert camera._box_x() == 300
