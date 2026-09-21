"""
public API of core.drone.
"""

from .base import DroneBase, DroneConState, DroneFlightState, DroneType


def get_drone(dronetype: DroneType, drone_id: str, **kwargs) -> DroneBase:
    """Create a new drone instance using the default implementation."""
    match dronetype:
        case DroneType.SIM_SIMDRONE:
            from core.drone.implementations.Sim.simdrone.simdrone import SimDrone

            return SimDrone(drone_type=dronetype, drone_id=drone_id, **kwargs)
        case DroneType.DJI_TELLO:
            from core.drone.implementations.DJI.tello.tello import TelloDrone

            return TelloDrone(drone_type=dronetype, drone_id=drone_id, **kwargs)
        case _:
            raise ValueError(f"Unknown drone type: {dronetype}")


__all__ = ["DroneType", "DroneFlightState", "DroneConState", "get_drone"]
