"""
SimpleBus - the default, in-process, asyncio-based implementation of
BusBase.

"In-process" is the key limitation to keep in mind: this bus only works
within a single Python process/asyncio event loop. If DroneFlightUltimate
ever needs to control drones from multiple machines, a different
implementation (e.g. one backed by a message queue over the network)
could be added here, alongside SimpleBus, as long as it also satisfies
BusBase - nothing else in the app would need to change.
"""

import asyncio
import inspect
from collections import defaultdict
from typing import Any

from core.bus.base import BusBase, Callback


class SimpleBus(BusBase):
    def __init__(self) -> None:
        self._subscribers: dict[str, list[Callback]] = defaultdict(list)

    def subscribe(self, topic: str, callback: Callback) -> None:
        self._subscribers[topic].append(callback)

    def unsubscribe(self, topic: str, callback: Callback) -> None:
        if callback in self._subscribers.get(topic, []):
            self._subscribers[topic].remove(callback)

    async def publish(self, topic: str, data: Any = None) -> None:
        callbacks = list(self._subscribers.get(topic, [])) + list(
            self._subscribers.get("*", [])
        )
        if not callbacks:
            return

        await asyncio.gather(*(self._invoke(cb, topic, data) for cb in callbacks))

    @staticmethod
    async def _invoke(callback: Callback, topic: str, data: Any) -> None:
        # Support both sync callbacks (e.g. a simple lambda appending to
        # a list) and async callbacks (e.g. a coroutine that awaits I/O)
        # with the same subscribe() call, so subscribers don't need to
        # care which kind they are writing.
        result = callback(topic, data)
        if inspect.isawaitable(result):
            await result