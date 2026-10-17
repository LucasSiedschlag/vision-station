"""Small measures shared by the tools: limits as scores, and the longest run along a strip.

A tool's score is the lowest of its criteria; each criterion is 1.0 when satisfied and falls towards 0 as
the measure moves past its limit, so the score is below 1 exactly when the tool fails.
"""

import numpy as np


def at_least(value: float, limit: float) -> float:
    return 1.0 if value >= limit else (value / limit if limit > 0 else 1.0)


def at_most(value: float, limit: float) -> float:
    if value <= limit or limit >= 1:
        return 1.0
    return max(0.0, (1 - value) / (1 - limit))


def longest_run(flags: np.ndarray) -> tuple[int, int]:
    """Start and length of the longest run of True."""
    padded = np.concatenate(([False], np.asarray(flags, bool), [False]))
    edges = np.flatnonzero(np.diff(padded.astype(np.int8)))
    if not len(edges):
        return 0, 0
    starts, ends = edges[::2], edges[1::2]
    i = int(np.argmax(ends - starts))
    return int(starts[i]), int(ends[i] - starts[i])


def strip_profile(covered: np.ndarray) -> dict:
    """Coverage, longest gap (ends included) and where it is, as fractions of the strip's length."""
    length = len(covered)
    if not length:
        return {"coverage": 0.0, "gap": 1.0, "gap_at": None}
    start, size = longest_run(~covered)
    return {"coverage": float(covered.mean()), "gap": size / length, "gap_at": [start / length, (start + size) / length] if size else None}
