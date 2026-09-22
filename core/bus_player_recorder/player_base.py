"""
PlayerBase - abstract interface for replaying a previously recorded
bus session back onto an EventBus.

Supports two modes that share the same read position:
  - play(): timed playback, respecting the original relative timing
    between events (scaled by `speed`), pausable via pause()/resume().
  - step(): publish exactly the next event immediately, ignoring
    timing - for manual, event-by-event debugging. Can be interleaved
    with play() (e.g. pause(), step() a few times, resume()).
"""

from abc import ABC, abstractmethod


class PlayerBase(ABC):
    @abstractmethod
    async def play(self, bus, speed: float = 1.0) -> None:
        """Replay all remaining recorded events onto `bus`, waiting
        between them according to their original relative timing,
        scaled by `speed`. Honors pause()/resume()."""
        raise NotImplementedError

    @abstractmethod
    async def step(self, bus) -> bool:
        """Publish exactly the next recorded event onto `bus`
        immediately, ignoring original timing. Returns False (and
        publishes nothing) once there are no more events."""
        raise NotImplementedError

    @abstractmethod
    def pause(self) -> None:
        """Pause a running play(). No-op if already paused."""
        raise NotImplementedError

    @abstractmethod
    def resume(self) -> None:
        """Resume a paused play(). No-op if not paused."""
        raise NotImplementedError
