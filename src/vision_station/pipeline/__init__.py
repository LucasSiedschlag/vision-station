"""The inspection pipeline: frame in, PASS / FAIL / ERROR out (architecture §7.1, FR-INS-*)."""

from vision_station.pipeline.inspect import inspect_job
from vision_station.pipeline.overlay import draw_overlay

__all__ = ["draw_overlay", "inspect_job"]
