"""Connects the station controller to the result store."""

import logging

from vision_station.records.store import ResultStore
from vision_station.station import StationEvent

log = logging.getLogger(__name__)


class ResultRecorder:
    """Pass an instance as `on_event=` to `StationController`: every result is recorded with its frame.

    A failure to record (disk full, locked database) is logged and counted but never stops the
    station; the screen can show `failures` as a warning.
    """

    def __init__(self, store: ResultStore, overlay=None):
        self.store = store
        self._overlay = overlay  # optional: (frame image, result) -> image with the problem marked
        self.failures = 0
        self.last_error: str | None = None

    def __call__(self, event: StationEvent) -> None:
        if event.kind != "result" or event.result is None:
            return
        try:
            image = event.frame.image if event.frame is not None else None
            overlay = self._overlay(image, event.result) if self._overlay and image is not None else None
            self.store.record(event.result, image, job_id=event.job_id, job_name=event.job_name, job_version=event.job_version, overlay=overlay)
        except Exception as exc:
            self.failures += 1
            self.last_error = f"{type(exc).__name__}: {exc}"
            log.exception("could not record the result")
