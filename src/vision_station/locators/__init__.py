"""Locators. Importing the package registers the built-in ones."""

from vision_station.locators import fixed as _fixed  # noqa: F401  (registers the locator)
from vision_station.locators.base import (
    Anchor,
    LocatorError,
    LocatorType,
    check_job_locator,
    get_locator,
    locator_types,
    register,
    run_locator,
    validate_params,
)

__all__ = ["Anchor", "LocatorError", "LocatorType", "check_job_locator", "get_locator", "locator_types", "register", "run_locator", "validate_params"]
