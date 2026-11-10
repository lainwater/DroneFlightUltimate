"""
pose - localization from mission pads in STANDARD right-handed frames.
Pure math (no drone, no bus) - tested in tests/more_examples/.

Standard frames (everything here, seen from above):
    right-handed: y = 90 deg counter-clockwise from x, z up
    yaw = counter-clockwise angle from +x in degrees, wrapped to -180 .. 180

    pad frame     origin = pad centre, +x = where the ROCKET points (DJI: "the rocket is +x"),
                  +y = left of the rocket, z up
    world frame   your room / board: pick an origin and an x axis, y 90 deg counter-clockwise, z up.
                  A pad's pose in the world = (x, y, rocket direction as yaw).

The Tello reports its pad reading (state["mission_pad"]) in its OWN pad frame, which is not
standard: y points to the RIGHT of the rocket and yaw turns CLOCKWISE. tello_to_standard()
converts it - the two signs below are the only place this is decided.
Check on the drone: hold it over a pad, move it LEFT of the rocket -> standard y must grow;
turn it counter-clockwise -> standard yaw must grow. If not, flip the sign.
"""

import math

Matrix = list[list[float]]

TELLO_PAD_Y_SIGN = -1  # Tello pad y points right of the rocket -> standard y (left) = -y
TELLO_PAD_YAW_SIGN = -1  # Tello yaw is clockwise -> standard yaw (counter-clockwise) = -yaw


def wrap_deg(a: float) -> float:
    """-> -180 .. 180."""
    return (a + 180.0) % 360.0 - 180.0


def pose_matrix(x: float, y: float, yaw_deg: float) -> Matrix:
    """2D homogeneous transform of a frame at (x, y) turned yaw_deg counter-clockwise:

    [ cos -sin  x ]
    [ sin  cos  y ]
    [  0    0   1 ]
    """
    yaw = math.radians(yaw_deg)
    c, s = math.cos(yaw), math.sin(yaw)
    return [[c, -s, x], [s, c, y], [0.0, 0.0, 1.0]]


def multiply_matrix(a: Matrix, b: Matrix) -> Matrix:
    """a · b (a is n×m, b is m×p -> n×p)."""
    if not a or not b or len(a[0]) != len(b):
        raise ValueError(f"cannot multiply {len(a)}x{len(a[0]) if a else 0} by {len(b)}x{len(b[0]) if b else 0}")
    return [[sum(a[i][k] * b[k][j] for k in range(len(b))) for j in range(len(b[0]))] for i in range(len(a))]


def matrix_to_pose(m: Matrix) -> tuple[float, float, float]:
    """Homogeneous transform -> (x, y, yaw deg)."""
    return m[0][2], m[1][2], wrap_deg(math.degrees(math.atan2(m[1][0], m[0][0])))


def tello_to_standard(reading: dict) -> tuple[float, float, float] | None:
    """Tello mission_pad reading {"x", "y", "yaw"} -> drone pose in the standard pad frame.
    None if there is no yaw (no pad seen)."""
    if reading.get("yaw") is None:
        return None
    return float(reading.get("x", 0)), TELLO_PAD_Y_SIGN * float(reading.get("y", 0)), wrap_deg(TELLO_PAD_YAW_SIGN * float(reading["yaw"]))


def world_pose(pad_in_world: tuple[float, float, float], reading: dict) -> tuple[float, float, float] | None:
    """Drone pose in the world from one pad's known world pose (x, y, rocket yaw) and the
    Tello's reading of that pad. -> (x cm, y cm, yaw deg), all standard."""
    drone_in_pad = tello_to_standard(reading)
    if drone_in_pad is None:
        return None
    world_T_drone = multiply_matrix(pose_matrix(*pad_in_world), pose_matrix(*drone_in_pad))
    return matrix_to_pose(world_T_drone)
