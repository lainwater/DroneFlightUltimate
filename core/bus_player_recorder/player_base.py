"""
PlayerBase - abstract interface for replaying a previously recorded
bus session back onto an EventBus (usually a fresh one, distinct from
the bus of the live flight it was recorded from).
"""
 
from abc import ABC, abstractmethod
 
 
class PlayerBase(ABC):
    @abstractmethod
    async def play(self, bus, speed: float = 1.0) -> None:
        """Replay all recorded events onto `bus`, waiting between them
        according to their original relative timing, scaled by
        `speed` (2.0 = twice as fast, 0.5 = half speed)."""
        raise NotImplementedError