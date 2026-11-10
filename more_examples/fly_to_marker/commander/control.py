"""
control - ArUco marker pose -> rc command (pure function, no drone, no bus).

Marker pose (from core.video's ArUco, OpenCV camera frame, metres):
    x right, y down, z forward (= distance straight ahead)
rc command (DFU rc frame, -1..1):
    x right, y forward, z up, yaw clockwise
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Gains:
    distance_m: float = 1.0  # stop this far in front of the marker
    k_forward: float = 0.4  # rc per metre of distance error
    k_up: float = 0.8  # rc per metre the marker is above/below the image centre
    k_yaw: float = 1.0  # rc per (x / z) - turn towards the marker
    max_rc: float = 0.3  # never faster than this
    deadband_m: float = 0.05  # errors smaller than this count as zero


def clamp(v: float, limit: float) -> float:
    return max(-limit, min(limit, v))


def _dead(v: float, band: float) -> float:
    return 0.0 if abs(v) < band else v


def rc_to_marker(marker: dict, g: Gains = Gains()) -> dict:
    """One marker (needs x, y, z) -> rc args {"x", "y", "z", "yaw"} that bring the drone
    to distance_m straight in front of it."""
    x, y, z = marker["x"], marker["y"], marker["z"]
    forward = _dead(z - g.distance_m, g.deadband_m) * g.k_forward
    up = -_dead(y, g.deadband_m) * g.k_up  # marker below centre (y > 0) -> go down
    yaw = (x / z if z > 0 else 0.0) * g.k_yaw  # marker right of centre -> turn right (clockwise)
    if abs(x) < g.deadband_m:
        yaw = 0.0
    return {k: round(clamp(v, g.max_rc), 3) for k, v in (("x", 0.0), ("y", forward), ("z", up), ("yaw", yaw))}


def arrived(marker: dict, g: Gains = Gains(), tolerance_m: float = 0.1) -> bool:
    """Close enough: at the distance and roughly centred."""
    return abs(marker["z"] - g.distance_m) < tolerance_m and abs(marker["x"]) < tolerance_m and abs(marker["y"]) < tolerance_m
