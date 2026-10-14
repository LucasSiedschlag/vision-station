"""The outcome of one inspection, as the station controller and the screen see it."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class Outcome(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    ERROR = "ERROR"  # the system could not inspect; never shown as PASS (FR-INS-6)


@dataclass(frozen=True)
class InspectionResult:
    outcome: Outcome
    reason: str = ""  # Portuguese, for the operator (FR-INS-7)
    scores: Mapping[str, float] = field(default_factory=dict)
    details: Mapping[str, Any] = field(default_factory=dict)
    duration_s: float = 0.0
