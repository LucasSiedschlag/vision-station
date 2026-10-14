"""Hands station events from the controller thread to the WebSocket clients."""

import asyncio
import threading
from typing import Any


class EventHub:
    """The controller calls `publish` from its thread; each connected client has a small queue that
    its coroutine drains. A slow client loses its oldest events instead of slowing the station."""

    def __init__(self, queue_size: int = 100):
        self._queue_size = queue_size
        self._clients: dict[asyncio.Queue, asyncio.AbstractEventLoop] = {}
        self._lock = threading.Lock()

    def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(self._queue_size)
        with self._lock:
            self._clients[queue] = asyncio.get_running_loop()
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        with self._lock:
            self._clients.pop(queue, None)

    @property
    def clients(self) -> int:
        with self._lock:
            return len(self._clients)

    def publish(self, message: dict[str, Any]) -> None:
        with self._lock:
            targets = list(self._clients.items())
        for queue, loop in targets:
            loop.call_soon_threadsafe(self._put, queue, message)

    @staticmethod
    def _put(queue: asyncio.Queue, message: dict[str, Any]) -> None:
        if queue.full():
            queue.get_nowait()
        queue.put_nowait(message)
