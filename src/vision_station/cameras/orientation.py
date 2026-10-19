"""The image orientation of a job's camera profile, applied to every frame (FR-ACQ-10, TD-32).

Mounting a camera upside down or seeing the part in a mirror is a property of the view, not of the part, so the
program turns the picture once, where frames enter (`station/acquisition.py`). Everything after that, the live view,
the reference image, the samples, the regions and the results, is in the oriented frame. None of the four turns
changes the size of the picture, so a region given as fractions of the frame stays where it is.
"""

import cv2
import numpy as np

from vision_station.jobs.camera_profile import Orientation

# the code `cv2.flip` takes: 1 mirrors left and right, 0 flips top and bottom, -1 does both (a turn of 180°)
_FLIP: dict[str, int] = {"mirror": 1, "flip": 0, "rotate180": -1}


def orient(image: np.ndarray, orientation: Orientation) -> np.ndarray:
    """The picture as the profile wants to see it; the same array when the orientation is normal."""
    code = _FLIP.get(orientation)
    return image if code is None else cv2.flip(image, code)
