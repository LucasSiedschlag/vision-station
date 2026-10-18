"""Connects the station controller to the result store."""

import logging
from collections.abc import Callable
from dataclasses import replace

from vision_station.core.i18n import render
from vision_station.records.store import ResultStore
from vision_station.station import StationEvent

log = logging.getLogger(__name__)


class ResultRecorder:
    """Pass an instance as `on_event=` to `StationController`: every result is recorded with its frame.

    A failure to record (disk full, locked database) is logged and counted but never stops the
    station; the screen can show `failures` as a warning.
    """

    def __init__(self, store: ResultStore, overlay=None, language: Callable[[], str] | None = None):
        self.store = store
        self._language = language  # the station language: the reason is recorded in the language it was shown in (TD-30)
        self._overlay = overlay  # optional: (frame image, result) -> image with the problem marked
        self.failures = 0
        self.last_error: str | None = None
        self.last_record_id: str | None = None  # of the result recorded last, for the screen

    def __call__(self, event: StationEvent) -> None:
        if event.kind != "result" or event.result is None:
            return
        self.last_record_id = None
        try:
            image = event.frame.image if event.frame is not None else None
            overlay = self._overlay(image, event.result) if self._overlay and image is not None else None
            result = event.result if self._language is None else replace(event.result, reason=render(event.result.reason, self._language()))
            record = self.store.record(result, image, job_id=event.job_id, job_name=event.job_name, job_version=event.job_version, overlay=overlay)
            self.last_record_id = record.id
        except Exception as exc:
            self.failures += 1
            self.last_error = f"{type(exc).__name__}: {exc}"
            log.exception("could not record the result")
