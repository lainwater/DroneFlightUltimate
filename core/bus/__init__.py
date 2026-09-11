"""
Public API of core.bus.

The rest of the app should always do:
    from core.bus import get_bus
    bus = get_bus()

...rather than importing SimpleBus directly, so the concrete
implementation stays swappable in one place.

Unlike core.fileops.get_fileops() (which caches a single instance
because it is stateless), get_bus() returns a NEW bus every time it is
called - each flight session/example gets its own bus instance,
explicitly passed to its controller, drone and video objects.
"""

from .base import BusBase, Callback


def get_bus() -> BusBase:
    """Create a new bus instance using the default implementation."""
    from .implementations.simple_bus import SimpleBus

    return SimpleBus()


__all__ = ["BusBase", "Callback", "get_bus"]