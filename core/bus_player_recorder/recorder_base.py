"""
RecorderBase - abstract interface for recording bus events for later
replay via a matching PlayerBase implementation.
"""
 
from abc import ABC, abstractmethod
 
 
class RecorderBase(ABC):
    @abstractmethod
    def attach(self, bus) -> None:
        """Start recording every event published on `bus`."""
        raise NotImplementedError
 
    @abstractmethod
    def detach(self, bus) -> None:
        """Stop recording events from `bus`. Must be a no-op (not an
        error) if the recorder was never attached."""
        raise NotImplementedError