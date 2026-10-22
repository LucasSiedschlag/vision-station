"""Locators. Importing the package registers the built-in ones."""

from vision_station.locators import blob as _blob  # noqa: F401  (registers the locators)
from vision_station.locators import edges as _edges  # noqa: F401
from vision_station.locators import fixed as _fixed  # noqa: F401
from vision_station.locators import template as _template  # noqa: F401
from vision_station.locators.base import (
    LocatorError,
    LocatorType,
    check_job_locator,
    get_locator,
    locator_types,
    register,
    run_locator,
    validate_params,
)

__all__ = ["LocatorError", "LocatorType", "check_job_locator", "get_locator", "locator_types", "register", "run_locator", "validate_params"]
