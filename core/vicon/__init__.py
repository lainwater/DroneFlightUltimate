"""
public API of core.vicon.

    from core.vicon import get_vicon
    vicon = get_vicon(drone_id="drone1", bus=bus, host="192.168.10.1:801", subject="tello-1")
    await vicon.start()     # publishes vicon.drone1 on the bus
    await vicon.stop()

See vicon_receiver.py for the bus contract.
"""

from .vicon_receiver import ViconReceiver, quat_to_euler_xyz


def get_vicon(drone_id: str, bus: object, **kwargs) -> ViconReceiver:
    """Create a Vicon receiver for one subject (kwargs: host, subject, segment, rate_hz)."""
    return ViconReceiver(drone_id=drone_id, bus=bus, **kwargs)


__all__ = ["ViconReceiver", "get_vicon", "quat_to_euler_xyz"]
