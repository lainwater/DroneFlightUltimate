"""
Public API of core.bus.

The rest of the app should always do:
    from core.bus import get_bus
    bus = get_bus()

Returns a NEW bus every time it is called - each session gets its own bus instance,
explicitly passed to its controller, drone etc. objects
"""

from .base import BusBase, Callback


def get_bus() -> BusBase:
    """Create a new bus instance using the default implementation."""
    from .implementations.simple_bus import SimpleBus

    return SimpleBus()


__all__ = ["BusBase", "Callback", "get_bus"]
