"""Locators: find the thing to inspect in the frame, so regions can be placed relative to it (TD-19, architecture §7.1).

A locator turns a frame into a *fixture* (`geometry.pose.Fixture`): where the object is, how it is turned and how large
it is, so regions can be placed in its own axes (architecture §14). A job without a locator uses only the frame.
Locator types are registered by name and version, like tools.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np
from pydantic import BaseModel, ValidationError

from vision_station.core.jobfiles import JobFileError, JobFiles, check_files
from vision_station.geometry.pose import Fixture
from vision_station.jobs import Job


class LocatorError(Exception):
    """A job refers to a locator the software cannot run, or gives it invalid parameters."""


@dataclass(frozen=True)
class LocatorType:
    name: str
    version: int
    params: type[BaseModel]
    locate: Callable[[np.ndarray, Any, JobFiles], Fixture | None]  # (image, validated params, job files) -> fixture in the image's own coordinates, or None
    needs: Callable[[Any], list[str]] = lambda params: []  # job files the validated params refer to


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


def run_locator(name: str, version: int, frame: np.ndarray, params: Mapping[str, Any], files: JobFiles | Mapping[str, bytes] | None = None) -> Fixture | None:
    locator = get_locator(name, version)
    return locator.locate(frame, validate_params(name, version, params), files if isinstance(files, JobFiles) else JobFiles(files))


def check_job_locator(job: Job, files: Mapping[str, bytes] | None = None) -> None:
    """Refuse a job whose locator this software cannot run, or (when the job's files are given) whose
    locator needs a file that is not there."""
    locator = job.geometry.locator
    if locator is not None:
        params = validate_params(locator.type, locator.version, locator.params)
        if files is not None:
            try:
                check_files(f"locator '{locator.type}'", get_locator(locator.type, locator.version).needs(params), files)
            except JobFileError as exc:
                raise LocatorError(str(exc)) from exc
