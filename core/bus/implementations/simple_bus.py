"""
SimpleBus - the default, asyncio-based implementation of
BusBase running in a single process/cooroutine.
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
        """Check if async or sync and awaits if it is async."""
        result = callback(topic, data)
        if inspect.isawaitable(result):
            await result