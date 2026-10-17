"""Inspections requested by another program (FR-INT-1): a trigger with an id, and its result and images.

The registry keeps the last requests in memory, with the frame and the overlay already encoded, so the
caller gets the picture of its own inspection even when the result store keeps only a sample of PASS
images. A request that does not turn into an inspection (the station stopped, the camera was lost)
expires; the caller must treat that as an error, never as a pass.
"""

import threading
import time
import uuid
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from vision_station.core.results import InspectionResult


@dataclass
class Requested:
    id: str
    reference: str
    requested_at: float  # time.time()
    result: InspectionResult | None = None
    record_id: str | None = None
    at: str | None = None
    job: tuple[str, str, int] | None = None  # id, name, version
    frame_jpeg: bytes | None = None
    overlay_jpeg: bytes | None = None
    done: threading.Event = field(default_factory=threading.Event)


class InspectionRegistry:
    def __init__(self, keep: int = 50, expire_s: float = 30.0, clock: Callable[[], float] = time.time):
        self._items: OrderedDict[str, Requested] = OrderedDict()
        self._keep = keep
        self.expire_s = expire_s
        self._clock = clock
        self._lock = threading.Lock()

    def new(self, reference: str) -> Requested:
        item = Requested(id=uuid.uuid4().hex, reference=reference, requested_at=self._clock())
        with self._lock:
            self._items[item.id] = item
            while len(self._items) > self._keep:
                self._items.popitem(last=False)
        return item

    def discard(self, id: str) -> None:
        """A request the station refused: it never existed for the caller."""
        with self._lock:
            self._items.pop(id, None)

    def get(self, id: str) -> Requested | None:
        with self._lock:
            return self._items.get(id)

    def status(self, item: Requested) -> str:
        if item.done.is_set():
            return "done"
        return "expired" if self._clock() - item.requested_at > self.expire_s else "pending"

    def complete(self, id: str, result: InspectionResult, **found: Any) -> None:
        item = self.get(id)
        if item is None or item.done.is_set():
            return
        item.result = result
        for key, value in found.items():
            setattr(item, key, value)
        item.done.set()
