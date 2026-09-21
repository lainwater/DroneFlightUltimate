"""
BusBase - abstract interface for the async publish/subscribe event bus.

The bus is the backbone of DroneFlightUltimate: no core module should
ever import another core module directly.
Everything communicates exclusively through topic strings on the bus.

Topic naming convention used throughout the app:
    cmd.{drone_id}      controller -> drone   (abstract commands)
    state.{drone_id}    drone -> everyone     (telemetry)
    video.{drone_id}    drone -> everyone     (raw frames)
    "*"                 wildcard, receives EVERY published event

Subscribers are always called with (topic, data), regardless of whether
they subscribed to an exact topic or the wildcard "*".
"""

from abc import ABC, abstractmethod
from typing import Any, Awaitable, Callable, Union

# A subscriber callback receives (topic, data) and may be sync or async.
Callback = Callable[[str, Any], Union[None, Awaitable[None]]]


class BusBase(ABC):
    @abstractmethod
    def subscribe(self, topic: str, callback: Callback) -> None:
        """Register callback to be invoked whenever `topic` is published.
        Pass "*" as topic to receive every event on the bus, regardless
        of its actual topic."""
        raise NotImplementedError

    @abstractmethod
    def unsubscribe(self, topic: str, callback: Callback) -> None:
        """Remove a previously registered callback. Must be a no-op
        (not an error) if the callback was never subscribed to that
        topic."""
        raise NotImplementedError 

    @abstractmethod
    async def publish(self, topic: str, data: Any = None) -> None:
        """Publish `data` under `topic`. Every subscriber to that exact
        topic AND every wildcard ("*") subscriber must be invoked.
        Implementations may run callbacks concurrently, but this
        coroutine should only return once all of them have completed -
        callers rely on `await bus.publish(...)` meaning "delivered",
        not just "queued"."""
        raise NotImplementedError