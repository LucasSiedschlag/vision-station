import cv2
import numpy
import pydantic
import yaml

import vision_station


def test_package_imports():
    assert vision_station.__version__ == "0.1.0"


def test_runtime_libraries_available():
    assert cv2.__version__
    assert numpy.__version__
    assert pydantic.VERSION.startswith("2.")
    assert yaml.safe_load("a: 1") == {"a": 1}
