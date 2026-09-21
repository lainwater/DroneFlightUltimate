"""
public API of core.drone.
"""

from .base import ControllerBase
from enum import Enum

class ControllerType(Enum):
    KEYBOARD_CONTROLLER = "keyboard_controller"
    REPL = "repl_controller"
    JoystickController = "JoystickController"

def get_controller(
    controllertype: ControllerType,
    drone_id: str,
    bus: object,
    layout: str | None = None,
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
        case ControllerType.JoystickController:
                    from .implementations.joystick_controller.joystick_controller import JoystickController
                    return JoystickController(drone_id=drone_id, bus=bus, layout=layout, **kwargs)
        case _:
            raise ValueError(f"Unknown Controller type: {controllertype}")


__all__ = ["ControllerBase", "ControllerType", "get_controller"]