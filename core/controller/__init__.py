"""
public API of core.drone.
"""

from .base import ControllerBase, ControllerType

def get_controller(
    controllertype: ControllerType,
    **kwargs
    ) -> ControllerBase:
    """Create a new drone instance using the default implementation."""
    match ControllerType:
        case ControllerType.KEYBOARD_CONTROLLER:
            from .implementations.keyboard_controller.keyboard_controller import KeyboardController
            return KeyboardController()
        case ControllerType.REPL:
            from .implementations.repl_controller.repl_controller import REPLController
            return REPLController()
        case _:
            raise ValueError(f"Unknown Controller type: {ControllerType}")


__all__ = ["ControllerBase", "ControllerType", "get_controller"]