"""
public API of core.controller
Create a controller instance with
```
    from core.controller import get_controller, Controller Typ
    controller = get_controller(controllertype=ControllerType.<selected_type>,
                                drone_id=<id>.
                                bus=<your_bus>,
                                layout=<your_layout>)
```
Available layouts per controller can be seen in docs or core/controller/implementation/<your_implementation>/<any>.json
"""

from .base import ControllerBase
from enum import Enum

class ControllerType(Enum):
    KEYBOARD_CONTROLLER = "keyboard_controller"
    REPL = "repl_controller"
    JOYSTICK = "JoystickController"

def get_controller(
    controllertype: ControllerType,
    drone_id: str,
    bus: object,
    layout: str | None = None,
    **kwargs
    ) -> ControllerBase:
    """Create a new controller instance."""
    match controllertype:
        case ControllerType.KEYBOARD_CONTROLLER:
            from .implementations.keyboard_controller.keyboard_controller import KeyboardController
            return KeyboardController(drone_id=drone_id, bus=bus, layout=layout, **kwargs)
        case ControllerType.REPL:
            from .implementations.repl_controller.repl_controller import REPLController
            return REPLController(drone_id=drone_id, bus=bus, layout=layout, **kwargs)
        case ControllerType.JOYSTICK:
            from .implementations.joystick_controller.joystick_controller import JoystickController
            return JoystickController(drone_id=drone_id, bus=bus, layout=layout, **kwargs)
        case _:
            raise ValueError(f"Unknown Controller type: {controllertype}")


__all__ = ["ControllerBase", "ControllerType", "get_controller"]