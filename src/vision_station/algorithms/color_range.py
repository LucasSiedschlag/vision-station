"""A color range proposed from sampled pixels (FR-UI-13, document 05 §19.4).

The person drags over the image: the pixels under *incluir* are the color, the pixels under *excluir* are what must
stay out (a label next to a blue cap). The hue is read around its circular middle, so a red that spans 170..10 is one
band; saturation and value are the same percentiles. Nothing here saves anything: the editor shows the range as a
proposal and applies it when the person says so.
"""

from dataclasses import dataclass

import cv2
import numpy as np

from vision_station.algorithms.color import ColorRange

LOW_Q, HIGH_Q = 2.0, 98.0  # the percentiles that bound the band: a stray pixel does not widen it
CHROMATIC = (40, 40)  # saturation and value from which a pixel has a hue worth keeping (grays and whites have none)
MIN_PIXELS = 10
MAX_PIXELS = 20_000  # pixels kept of each side: the same band to the eye, and fast
LEAK_OK = 0.02  # this share of the excluded pixels inside the range is "out"
KEEP_MIN = 0.70  # tightening to leave the excluded pixels out never gives up more than this of the colour
HUE_STEP, LEVEL_STEP = 2, 8
MIN_HUE_SPAN = 8  # a band narrower than this (16 degrees) is finer than the noise of any camera: a flat patch still gets a usable one
MIN_LEVEL_SPAN = 48


@dataclass(frozen=True)
class RangeProposal:
    hue: tuple[int, int] | None
    s_min: int
    s_max: int
    v_min: int
    v_max: int
    pixels: int  # of the colour that was sampled
    kept: float  # share of them inside the proposed range
    leak: float | None  # share of the excluded pixels inside it; None: nothing was excluded


def _hsv(images: list[np.ndarray]) -> np.ndarray:
    pixels = np.concatenate([cv2.cvtColor(i, cv2.COLOR_BGR2HSV).reshape(-1, 3) for i in images if i.size]) if images else np.zeros((0, 3), np.uint8)
    if len(pixels) > MAX_PIXELS:
        pixels = pixels[np.linspace(0, len(pixels) - 1, MAX_PIXELS).astype(int)]
    return pixels.astype(np.int16)


def _inside(hsv: np.ndarray, hue: tuple[int, int] | None, s: tuple[int, int], v: tuple[int, int]) -> np.ndarray:
    ok = (hsv[:, 1] >= s[0]) & (hsv[:, 1] <= s[1]) & (hsv[:, 2] >= v[0]) & (hsv[:, 2] <= v[1])
    if hue is not None:
        lo, hi = hue
        ok &= ((hsv[:, 0] >= lo) & (hsv[:, 0] <= hi)) if lo <= hi else ((hsv[:, 0] >= lo) | (hsv[:, 0] <= hi))
    return ok


def _signed(h: np.ndarray, centre: int) -> np.ndarray:
    """The hue's distance from `centre` on the circle of 180, in -90..89."""
    return (h - centre + 90) % 180 - 90


def propose_range(include: list[np.ndarray], exclude: list[np.ndarray] | None = None) -> RangeProposal | None:
    """The range of the colour in `include` (BGR crops), kept off `exclude`. None when there is too little to go on."""
    colour = _hsv(include)
    if len(colour) < MIN_PIXELS:
        return None
    saturated = (colour[:, 1] >= CHROMATIC[0]) & (colour[:, 2] >= CHROMATIC[1])
    hue: tuple[int, int] | None = None
    basis = colour
    if saturated.mean() >= 0.5:
        basis = colour[saturated]
        angles = basis[:, 0] / 180 * 2 * np.pi
        centre = int(round((np.arctan2(np.sin(angles).sum(), np.cos(angles).sum()) / (2 * np.pi) * 180))) % 180
        offsets = _signed(basis[:, 0], centre)
        lo, hi = int(np.floor(np.percentile(offsets, LOW_Q))), int(np.ceil(np.percentile(offsets, HIGH_Q)))
        if hi - lo < MIN_HUE_SPAN:
            lo, hi = lo - (MIN_HUE_SPAN - (hi - lo) + 1) // 2, hi + (MIN_HUE_SPAN - (hi - lo)) // 2
        hue = ((centre + lo) % 180, (centre + hi) % 180)

    def bounds(column: int) -> tuple[int, int]:
        lo, hi = int(np.floor(np.percentile(basis[:, column], LOW_Q))), int(np.ceil(np.percentile(basis[:, column], HIGH_Q)))
        if hi - lo < MIN_LEVEL_SPAN:
            grow = MIN_LEVEL_SPAN - (hi - lo)
            lo, hi = max(0, lo - grow // 2), min(255, hi + (grow + 1) // 2)
        return lo, 255 if hi >= 235 else hi  # an upper limit that high only cuts the highlights

    s, v = bounds(1), bounds(2)
    leak: float | None = None
    out = _hsv(exclude or [])
    if len(out):
        hue, s, v = _keep_out(colour, out, hue, s, v)
        leak = float(_inside(out, hue, s, v).mean())
    kept = float(_inside(colour, hue, s, v).mean())
    return RangeProposal(hue=hue, s_min=s[0], s_max=s[1], v_min=v[0], v_max=v[1], pixels=len(colour), kept=kept, leak=leak)


def _keep_out(colour, out, hue, s, v):
    """Tighten one edge at a time, the one that drives most of the excluded pixels out for the least colour, until
    they are out (or the colour would be given up)."""
    have = len(colour)
    for _ in range(80):
        if _inside(out, hue, s, v).mean() <= LEAK_OK:
            break
        here = _inside(out, hue, s, v).sum()
        best, best_score = None, 0.0
        for move in _moves(hue, s, v):
            h2, s2, v2 = move
            kept = _inside(colour, h2, s2, v2).sum() / have
            if kept < KEEP_MIN:
                continue
            score = (here - _inside(out, h2, s2, v2).sum()) / len(out) - 0.25 * (_inside(colour, hue, s, v).sum() - kept * have) / have
            if score > best_score:
                best, best_score = move, score
        if best is None:
            break
        hue, s, v = best
    return hue, s, v


def _moves(hue, s, v):
    if hue is not None:
        lo, hi = hue
        width = (hi - lo) % 180
        if width > 2 * HUE_STEP:
            yield ((lo + HUE_STEP) % 180, hi), s, v
            yield (lo, (hi - HUE_STEP) % 180), s, v
    if s[1] - s[0] > LEVEL_STEP:
        yield hue, (s[0] + LEVEL_STEP, s[1]), v
        yield hue, (s[0], s[1] - LEVEL_STEP), v
    if v[1] - v[0] > LEVEL_STEP:
        yield hue, s, (v[0] + LEVEL_STEP, v[1])
        yield hue, s, (v[0], v[1] - LEVEL_STEP)


def as_color_range(p: RangeProposal) -> ColorRange:
    """The proposal as the parameters the color tool takes (so the tool's own validation has the last word)."""
    return ColorRange(mode="range", hue=p.hue, s_min=p.s_min, s_max=p.s_max, v_min=p.v_min, v_max=p.v_max)
