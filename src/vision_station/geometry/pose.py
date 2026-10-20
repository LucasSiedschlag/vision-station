"""Fixtures and poses: the part's own coordinate system (architecture §14, TD-21, FR-INS-11).

A locator finds a *fixture*: where the object is (its centre), how it is turned (`angle`, degrees, counter-clockwise on the
screen) and how large it is against what was taught (`scale`). Regions are fractions of the fixture's **taught size**, in
the fixture's own axes. A tool never sees the rotation: `cut` takes the region out of the frame as an **upright** picture
(`cv2.warpAffine`, bilinear), so a part that arrives turned is judged as the one that arrived straight.

The fixture is kept the way the locators have always given it, a rectangle in fractions of the frame, plus the angle and
the scale. For an upright fixture at scale 1 (every format-1 job, and every part that is placed as taught) the region is
cut with the same arithmetic as before, expression by expression, so a job gives the same numbers as it did without
poses. The geometry of a turned fixture is done in pixels, because a rotation in fractions of a frame that is not square
would shear.
"""

import math
from dataclasses import dataclass

import cv2
import numpy as np

PixelRect = tuple[int, int, int, int]  # x0, y0, x1, y1
FractionRect = tuple[float, float, float, float]


@dataclass(frozen=True)
class Fixture:
    """What a locator found. `rect` is the taught box, centred on the pose, as fractions of the frame, **before** the
    scale and the angle are applied: where the object would be if it were exactly as taught."""

    rect: FractionRect
    angle: float = 0.0  # degrees, counter-clockwise on the screen, in (-180, 180]
    scale: float = 1.0  # found size / taught size
    score: float = 1.0  # how sure the locator is, 0..1
    name: str = "anchor"

    @property
    def upright(self) -> bool:
        """Placed as taught: the region is a plain slice of the frame, as it was before poses existed."""
        return self.angle == 0.0 and self.scale == 1.0

    @property
    def centre(self) -> tuple[float, float]:
        """The origin of the pose, fractions of the frame."""
        return (self.rect[0] + self.rect[2]) / 2, (self.rect[1] + self.rect[3]) / 2

    def corners(self, shape: tuple[int, ...]) -> np.ndarray:
        """The four corners of the found box in frame pixels, clockwise from the top-left one before turning."""
        height, width = shape[:2]
        x0, y0, x1, y1 = self.rect
        cx, cy = (x0 + x1) / 2 * width, (y0 + y1) / 2 * height
        w, h = (x1 - x0) * width * self.scale, (y1 - y0) * height * self.scale
        local = np.array([[-w / 2, -h / 2], [w / 2, -h / 2], [w / 2, h / 2], [-w / 2, h / 2]])
        return _turn(local, self.angle) + (cx, cy)

    def bounds(self, shape: tuple[int, ...]) -> FractionRect:
        """The smallest upright box around the found one, fractions of the frame: what the API and the overlay draw
        when they do not draw the turned outline. For an upright fixture it is `rect`, untouched."""
        if self.upright:
            return self.rect
        height, width = shape[:2]
        pts = self.corners(shape)
        return (
            float(pts[:, 0].min() / width),
            float(pts[:, 1].min() / height),
            float(pts[:, 0].max() / width),
            float(pts[:, 1].max() / height),
        )


@dataclass(frozen=True)
class Cut:
    """A region taken out of the frame."""

    image: np.ndarray  # upright, in the region's own axes
    px: PixelRect  # the smallest upright box around it in frame pixels
    corners: tuple[tuple[float, float], ...]  # its four corners in frame pixels (equal to `px` when it is not turned)
    #: maps a point of `image` (x, y in its pixels) to frame pixels; the identity plus an offset when not turned
    to_frame: np.ndarray  # 2x3


class RegionOutside(ValueError):
    """The region is not entirely inside the picture."""


def _turn(points: np.ndarray, angle: float) -> np.ndarray:
    """Points turned by `angle` degrees counter-clockwise *on the screen* (y grows downwards)."""
    a = math.radians(angle)
    c, s = math.cos(a), math.sin(a)
    x, y = points[:, 0], points[:, 1]
    return np.stack([x * c + y * s, -x * s + y * c], axis=1)


def pixel_rect(rect: FractionRect, shape: tuple[int, ...]) -> PixelRect:
    height, width = shape[:2]
    return (round(rect[0] * width), round(rect[1] * height), round(rect[2] * width), round(rect[3] * height))


def inside(px: PixelRect, shape: tuple[int, ...]) -> bool:
    height, width = shape[:2]
    return not (px[2] - px[0] < 1 or px[3] - px[1] < 1 or px[0] < 0 or px[1] < 0 or px[2] > width or px[3] > height)


def region_in_frame(rect: FractionRect, fixture: Fixture | None) -> FractionRect:
    """For an upright fixture: the region `rect` (fractions of the fixture's box) as fractions of the frame. With no
    fixture the region is already in the frame. The expression is the one the pipeline has always used."""
    if fixture is None:
        return rect
    ax0, ay0, ax1, ay1 = fixture.rect
    w, h = ax1 - ax0, ay1 - ay0
    x0, y0, x1, y1 = rect
    return (ax0 + x0 * w, ay0 + y0 * h, ax0 + x1 * w, ay0 + y1 * h)


def cut(image: np.ndarray, rect: FractionRect, fixture: Fixture | None) -> Cut:
    """The region `rect` of `fixture` (of the frame when `fixture` is None) as an upright picture. Raises `RegionOutside`."""
    shape = image.shape
    height, width = shape[:2]
    if fixture is None or fixture.upright:
        px = pixel_rect(region_in_frame(rect, fixture), shape)
        if not inside(px, shape):
            raise RegionOutside
        x0, y0, x1, y1 = px
        corners = ((float(x0), float(y0)), (float(x1), float(y0)), (float(x1), float(y1)), (float(x0), float(y1)))
        return Cut(image[y0:y1, x0:x1], px, corners, np.array([[1.0, 0.0, x0], [0.0, 1.0, y0]]))

    fx0, fy0, fx1, fy1 = fixture.rect
    fw, fh = (fx1 - fx0) * width * fixture.scale, (fy1 - fy0) * height * fixture.scale
    cx, cy = (fx0 + fx1) / 2 * width, (fy0 + fy1) / 2 * height
    x0, y0, x1, y1 = rect
    # the region's box in the fixture's axes, origin at the fixture's centre
    local = np.array([[x0 * fw - fw / 2, y0 * fh - fh / 2], [x1 * fw - fw / 2, y0 * fh - fh / 2], [x1 * fw - fw / 2, y1 * fh - fh / 2], [x0 * fw - fw / 2, y1 * fh - fh / 2]])
    corners = _turn(local, fixture.angle) + (cx, cy)
    out_w, out_h = max(1, round((x1 - x0) * fw)), max(1, round((y1 - y0) * fh))
    box = (
        math.floor(corners[:, 0].min()),
        math.floor(corners[:, 1].min()),
        math.ceil(corners[:, 0].max()),
        math.ceil(corners[:, 1].max()),
    )
    eps = 0.5  # half a pixel of rounding is not "outside"
    if corners[:, 0].min() < -eps or corners[:, 1].min() < -eps or corners[:, 0].max() > width + eps or corners[:, 1].max() > height + eps or (x1 - x0) * fw < 1 or (y1 - y0) * fh < 1:
        raise RegionOutside
    # output pixel (i, j) -> frame: turn its offset from the output centre, add the region's centre
    centre = _turn(np.array([[(x0 + x1) / 2 * fw - fw / 2, (y0 + y1) / 2 * fh - fh / 2]]), fixture.angle)[0] + (cx, cy)
    a = math.radians(fixture.angle)
    c, s = math.cos(a), math.sin(a)
    # frame_x = centre_x + (i - (out_w-1)/2)*c + (j - (out_h-1)/2)*s ; frame_y = centre_y - (i - ..)*s + (j - ..)*c
    ox, oy = (out_w - 1) / 2, (out_h - 1) / 2
    matrix = np.array([[c, s, centre[0] - ox * c - oy * s], [-s, c, centre[1] + ox * s - oy * c]])
    upright = cv2.warpAffine(image, matrix, (out_w, out_h), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP, borderMode=cv2.BORDER_REPLICATE)
    return Cut(upright, box, tuple((float(px), float(py)) for px, py in corners), matrix)


def compose(parent: Cut, parent_fixture: Fixture | None, child: Fixture, shape: tuple[int, ...]) -> Fixture:
    """A fixture found **inside** a parent's upright cut, as a fixture of the frame: its centre taken through the cut's map to
    the frame, its angle added to the parent's, its box expressed again in fractions of the frame (a chain, FR-INS-12)."""
    height, width = shape[:2]
    cut_h, cut_w = parent.image.shape[:2]
    x0, y0, x1, y1 = child.rect
    mx, my = (x0 + x1) / 2 * cut_w, (y0 + y1) / 2 * cut_h
    fx = parent.to_frame[0, 0] * mx + parent.to_frame[0, 1] * my + parent.to_frame[0, 2]
    fy = parent.to_frame[1, 0] * mx + parent.to_frame[1, 1] * my + parent.to_frame[1, 2]
    w_px, h_px = (x1 - x0) * cut_w, (y1 - y0) * cut_h  # the cut has the frame's pixels: sizes carry over unchanged
    angle = child.angle + (0.0 if parent_fixture is None else parent_fixture.angle)
    angle = (angle + 180.0) % 360.0 - 180.0
    rect = (fx / width - w_px / 2 / width, fy / height - h_px / 2 / height, fx / width + w_px / 2 / width, fy / height + h_px / 2 / height)
    return Fixture(rect=rect, angle=angle, scale=child.scale, score=child.score, name=child.name)
