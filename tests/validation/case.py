"""What a tool or locator type brings to the validation bench (architecture §15.3, VIA-0074).

Each type has a file in `cases/` named after it, with `TOOLS` and/or `LOCATORS`: a `Case` by version. The generic
checks need nothing else; golden images with their known answers (V2) are added to the same `Case`.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass(frozen=True)
class Golden:
    """A picture with a known answer (V2). A tool: the verdict and the measures it must give. A locator: where the
    object is, or that it is not there. `params` are laid over the case's, `files` replace its files."""

    id: str
    image: np.ndarray
    params: Mapping[str, Any] = field(default_factory=dict)
    files: Mapping[str, bytes] | None = None
    passed: bool | None = None  # a tool
    values: Mapping[str, float | str] = field(default_factory=dict)  # a tool: the measures, a number to `tolerance` or a text
    rect: tuple[float, float, float, float] | None = None  # a locator: the object, fractions of the frame
    tolerance: float = 0.01
    #: a tool: the marks it must draw, (kind, role, box of its points in the region's pixels), in order; None: not checked
    marks: tuple[tuple[str, str, tuple[float, float, float, float]], ...] | None = None
    mark_tolerance: float = 2.0  # pixels, on each side of the box


@dataclass(frozen=True)
class Scene:
    """A locator's picture with its object at the centre of the frame, and where it is."""

    frame: np.ndarray
    rect: tuple[float, float, float, float]  # the object, as fractions of the frame
    follows: bool = True  # False: the locator does not look at the picture (`fixed`), so a move or a turn is not its business


@dataclass(frozen=True)
class Case:
    params: Mapping[str, Any]  # valid parameters, the least a job needs
    files: Mapping[str, bytes] = field(default_factory=dict)  # the job files the parameters name
    bad_params: tuple[Mapping[str, Any], ...] = ()  # invalid combinations the type must refuse (V1)
    passing: np.ndarray | None = None  # a tool: a region that passes with `params`
    failing: np.ndarray | None = None  # a tool: a region that fails with `params`
    scene: Scene | None = None  # a locator: a frame that it must find the object in
    goldens: tuple[Golden, ...] = ()  # pictures with known answers
    draws_nothing: str = ""  # a tool that gives no marks says why (V7): the region outline is its drawing
    nothing_on_fail: str = ""  # the `failing` region has nothing to draw (the tool failed by not finding): why (V7)
