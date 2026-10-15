"""Locators: find the thing to inspect in the frame, so regions can be placed relative to it (TD-19, architecture §7.1).

A locator turns a frame into an *anchor*: a rectangle, as fractions of the frame, that regions can be relative
to. A job without a locator uses only the frame. Locator types are registered by name and version, like tools.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np
from pydantic import BaseModel, ValidationError

from vision_station.jobs import Job


class LocatorError(Exception):
    """A job refers to a locator the software cannot run, or gives it invalid parameters."""


@dataclass(frozen=True)
class Anchor:
    rect: tuple[float, float, float, float]  # x0, y0, x1, y1 as fractions of the frame
    score: float = 1.0  # how sure the locator is, 0..1


@dataclass(frozen=True)
class LocatorType:
    name: str
    version: int
    params: type[BaseModel]
    locate: Callable[[np.ndarray, Any], Anchor | None]  # (frame, validated params) -> anchor, or None if not found


_REGISTRY: dict[tuple[str, int], LocatorType] = {}


def register(locator: LocatorType) -> LocatorType:
    key = (locator.name, locator.version)
    if key in _REGISTRY:
        raise ValueError(f"locator {locator.name} v{locator.version} already registered")
    _REGISTRY[key] = locator
    return locator


def locator_types() -> list[tuple[str, int]]:
    return sorted(_REGISTRY)


def get_locator(name: str, version: int) -> LocatorType:
    found = _REGISTRY.get((name, version))
    if found is None:
        known = [v for (n, v) in _REGISTRY if n == name]
        if known:
            raise LocatorError(f"locator '{name}' version {version} is not supported (supported: {sorted(known)})")
        raise LocatorError(f"unknown locator '{name}' (available: {sorted({n for n, _ in _REGISTRY})})")
    return found


def validate_params(name: str, version: int, params: Mapping[str, Any]) -> BaseModel:
    locator = get_locator(name, version)
    try:
        return locator.params.model_validate(dict(params))
    except ValidationError as exc:
        raise LocatorError(f"invalid parameters for locator '{name}' v{version}: {exc}") from exc


def run_locator(name: str, version: int, frame: np.ndarray, params: Mapping[str, Any]) -> Anchor | None:
    locator = get_locator(name, version)
    return locator.locate(frame, validate_params(name, version, params))


def check_job_locator(job: Job) -> None:
    """Refuse a job whose locator this software cannot run."""
    locator = job.geometry.locator
    if locator is not None:
        validate_params(locator.type, locator.version, locator.params)
