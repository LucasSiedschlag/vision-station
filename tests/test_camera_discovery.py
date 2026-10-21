"""Which USB cameras are connected and which of them are validated (VIA-0068, S4)."""

from vision_station.cameras.discovery import VALIDATED_MODELS, discover, validated_model

C920 = ("HD Pro Webcam C920", r"\\?\usb#vid_046d&pid_082d#a")


def test_only_the_c920_is_validated_for_now():
    assert [m.id for m in VALIDATED_MODELS] == ["c920"]


def test_a_validated_camera_is_known_by_its_name_whatever_the_case():
    assert validated_model("HD Pro Webcam C920").id == "c920"
    assert validated_model("logitech c920 hd").id == "c920"
    assert validated_model("Integrated Camera") is None


def test_each_camera_found_says_how_to_open_it_and_whether_it_is_validated():
    found = discover(lambda: [C920, ("Integrated Camera", r"\\?\usb#vid_04f2#b")])
    assert found.available is True
    first, second = found.cameras
    assert (first.driver, first.connection, first.name, first.model) == ("uvc", {"device_name": "HD Pro Webcam C920"}, "HD Pro Webcam C920", "c920")
    assert second.model is None and second.connection == {"device_name": "Integrated Camera"}


def test_two_cameras_with_the_same_name_are_told_apart_by_their_path():
    one, two = discover(lambda: [C920, ("HD Pro Webcam C920", r"\\?\usb#vid_046d&pid_082d#b")]).cameras
    assert one.connection == {"device_path": C920[1]} and two.connection == {"device_path": r"\\?\usb#vid_046d&pid_082d#b"}
    assert one.model == two.model == "c920"


def test_no_cameras_is_not_the_same_as_not_being_able_to_look():
    assert discover(lambda: []).available is True and discover(lambda: []).cameras == []
    nothing = discover(lambda: None)  # the library that lists them is not here (not Windows)
    assert nothing.available is False and nothing.cameras == []


def test_a_listing_that_fails_counts_as_not_being_able_to_look():
    def broken():
        raise OSError("the driver did not answer")

    assert discover(broken).available is False
