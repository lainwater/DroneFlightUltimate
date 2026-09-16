"""
public API of core.drone.
"""

from .base import ControllerBase
from enum import Enum

class ControllerType(Enum):
    KEYBOARD_CONTROLLER = "keyboard_controller"
    REPL = "repl_controller"
    T8L = "t8l"

def get_controller(
    controllertype: ControllerType,
    drone_id: str,
    bus: object,
    layout: str = None,
    **kwargs
    ) -> ControllerBase:
    """Create a new drone instance using the default implementation."""
    match controllertype:
        case ControllerType.KEYBOARD_CONTROLLER:
            from .implementations.keyboard_controller.keyboard_controller import KeyboardController
            return KeyboardController(drone_id=drone_id, bus=bus, layout=layout, **kwargs)
        case ControllerType.REPL:
            from .implementations.repl_controller.repl_controller import REPLController
            return REPLController(drone_id=drone_id, bus=bus, layout=layout, **kwargs)
        case ControllerType.T8L:
                    from .implementations.rm_t8l.t8l_controller import T8LController
                    return T8LController(drone_id=drone_id, bus=bus, layout=layout, **kwargs)
        case _:
            raise ValueError(f"Unknown Controller type: {controllertype}")


__all__ = ["ControllerBase", "ControllerType", "get_controller"]