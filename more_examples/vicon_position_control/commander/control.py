"""
control - Vicon pose + target -> rc command (pure function, no drone, no bus).

Vicon world frame (lab): x, y horizontal, z up, millimetres; yaw counter-clockwise
seen from above, degrees, 0 = the subject's local x axis along world x.
The subject must be defined in Vicon Tracker with its local x axis = the drone's
nose (otherwise set yaw_offset_deg).

rc command (DFU rc frame, -1..1): x right, y forward, z up, yaw clockwise.
"""

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Gains:
    k_xy: float = 0.0015  # rc per mm horizontal error (1 m off -> 1.5 -> clamped to max_rc)
    k_z: float = 0.002  # rc per mm height error
    k_yaw: float = 0.01  # rc per degree yaw error
    max_rc: float = 0.3
    max_yaw_rc: float = 0.4
    deadband_mm: float = 30.0
    deadband_deg: float = 3.0
    yaw_offset_deg: float = 0.0  # nose direction vs. the subject's local x axis


def wrap_deg(a: float) -> float:
    """-> -180 .. 180."""
    return (a + 180.0) % 360.0 - 180.0


def world_to_body(ex: float, ey: float, yaw_deg: float) -> tuple[float, float]:
    """World error (mm) -> (right, forward) for a drone whose nose points at yaw_deg (counter-clockwise from +x)."""
    yaw = math.radians(yaw_deg)
    forward = ex * math.cos(yaw) + ey * math.sin(yaw)
    right = ex * math.sin(yaw) - ey * math.cos(yaw)
    return right, forward


def rc_to_target(pose: dict, target: dict, g: Gains = Gains()) -> dict:
    """pose: vicon.<id> data {"x","y","z","yaw"}; target: {"x","y","z"} (mm) and optional "yaw" (deg).
    -> rc args {"x","y","z","yaw"}."""
    heading = pose["yaw"] + g.yaw_offset_deg
    ex, ey, ez = target["x"] - pose["x"], target["y"] - pose["y"], target["z"] - pose["z"]
    if math.hypot(ex, ey) < g.deadband_mm:
        ex = ey = 0.0
    if abs(ez) < g.deadband_mm:
        ez = 0.0
    right, forward = world_to_body(ex, ey, heading)
    yaw_rc = 0.0
    if target.get("yaw") is not None:
        eyaw = wrap_deg(target["yaw"] - heading)  # counter-clockwise positive
        if abs(eyaw) >= g.deadband_deg:
            yaw_rc = -eyaw * g.k_yaw  # rc yaw is clockwise positive

    def clamp(v: float, limit: float) -> float:
        return round(max(-limit, min(limit, v)), 3)

    return {
        "x": clamp(right * g.k_xy, g.max_rc),
        "y": clamp(forward * g.k_xy, g.max_rc),
        "z": clamp(ez * g.k_z, g.max_rc),
        "yaw": clamp(yaw_rc, g.max_yaw_rc),
    }


def distance_mm(pose: dict, target: dict) -> float:
    return math.sqrt(sum((target[k] - pose[k]) ** 2 for k in ("x", "y", "z")))
