"""
control - ArUco marker pose -> rc command (pure function, no drone, no bus).

Marker pose (from core.video's ArUco, OpenCV camera frame, metres):
    x right, y down, z forward (= distance straight ahead)
    rvec/tvec: the marker's rotation/position in the camera frame
Marker's own frame (OpenCV ArUco):
    x right, y up, z out of the marker (towards whoever looks at it head-on)
rc command (DFU rc frame, -1..1):
    x right, y forward, z up, yaw clockwise
"""

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Gains:
    distance_m: float = 1.0  # stop this far in front of the marker
    k_forward: float = 0.4  # rc per metre of distance error
    k_up: float = 0.7  # rc per metre the marker is above/below the image centre
    k_yaw: float = 1.0  # rc per (x / z) - turn towards the marker
    k_side: float = 0.4  # rc per metre the drone is beside the marker's centre line
    max_rc: float = 0.3  # never faster than this
    deadband_m: float = 0.05  # errors smaller than this count as zero


def clamp(v: float, limit: float) -> float:
    return max(-limit, min(limit, v))


def _dead(v: float, band: float) -> float:
    return 0.0 if abs(v) < band else v


def side_offset(marker: dict) -> float:
    """How far the drone is beside the marker's centre line, in metres, in the marker's frame:
    > 0 = drone is on the marker's right (as seen standing in front of it), < 0 = on its left.

    Drone position in marker frame p = -R^T t (R from rvec). Only p_x is needed:
    p_x = -(first column of R) . t. R's first column via Rodrigues
    Uses rvec instead of roll/pitch/yaw"""
    rx, ry, rz = marker["rvec"]
    tx, ty, tz = marker["tvec"]
    theta = math.sqrt(rx * rx + ry * ry + rz * rz)
    if theta < 1e-9:
        col0 = (1.0, 0.0, 0.0)
    else:
        kx, ky, kz = rx / theta, ry / theta, rz / theta
        c, s = math.cos(theta), math.sin(theta)
        # R e_x = cos*e_x + (1-cos)*k*kx + sin*(k x e_x),  k x e_x = (0, kz, -ky)
        col0 = (c + (1 - c) * kx * kx, (1 - c) * ky * kx + s * kz, (1 - c) * kz * kx - s * ky)
    return -(col0[0] * tx + col0[1] * ty + col0[2] * tz)


def rc_to_marker(marker: dict, g: Gains = Gains()) -> dict:
    """One marker (needs x, y, z, rvec, tvec) -> rc args {"x", "y", "z", "yaw"} that bring the
    drone to distance_m straight in front of it.

    Sideways: slide towards the marker's centre line while yaw keeps the marker in the middle
    of the image - together that is an arc around the marker that ends in front of it."""
    x, y, z = marker["x"], marker["y"], marker["z"]
    forward = _dead(z - g.distance_m, g.deadband_m) * g.k_forward
    up = -_dead(y, g.deadband_m) * g.k_up  # marker below centre (y > 0) -> go down
    side = -_dead(side_offset(marker), g.deadband_m) * g.k_side  # drone on marker's right -> slide left
    yaw = (x / z if z > 0 else 0.0) * g.k_yaw  # marker right of centre -> turn right (clockwise)
    if abs(x) < g.deadband_m:
        yaw = 0.0
    return {k: round(clamp(v, g.max_rc), 3) for k, v in (("x", side), ("y", forward), ("z", up), ("yaw", yaw))}


def arrived(marker: dict, g: Gains = Gains(), tolerance_m: float = 0.1) -> bool:
    """Close enough: at the distance, roughly centred in the image and on the marker's centre line."""
    return (
        abs(marker["z"] - g.distance_m) < tolerance_m
        and abs(marker["x"]) < tolerance_m
        and abs(marker["y"]) < tolerance_m
        and abs(side_offset(marker)) < tolerance_m
    )
