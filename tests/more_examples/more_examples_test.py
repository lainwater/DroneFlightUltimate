"""Pure logic of more_examples (control laws, pose math, ...) - no drone needed."""

import math
from pathlib import Path

import pytest
from conftest import load_helper

MORE = Path(__file__).resolve().parents[2] / "more_examples"
marker = load_helper(MORE / "fly_to_marker/commander/control.py", "_t_marker_control")
vicon = load_helper(MORE / "vicon_position_control/commander/control.py", "_t_vicon_control")
pose = load_helper(MORE / "edu_pad_pose_orbit/commander/pose.py", "_t_pose")


# ------------------------------------------------------------ fly_to_marker
def test_marker_far_ahead_flies_forward():
    rc = marker.rc_to_marker({"x": 0.0, "y": 0.0, "z": 2.0})
    assert rc["y"] > 0 and rc["x"] == rc["z"] == rc["yaw"] == 0


def test_marker_too_close_backs_off_and_is_clamped():
    rc = marker.rc_to_marker({"x": 0.0, "y": 0.0, "z": 0.2})
    assert rc["y"] == -0.3


def test_marker_right_and_below():
    rc = marker.rc_to_marker({"x": 0.3, "y": 0.2, "z": 1.0})
    assert rc["yaw"] > 0 and rc["z"] < 0  # turn right (clockwise), go down


def test_marker_arrived():
    m = {"x": 0.02, "y": -0.03, "z": 1.04}
    assert marker.arrived(m) and marker.rc_to_marker(m) == {"x": 0.0, "y": 0.0, "z": 0.0, "yaw": 0.0}


# ------------------------------------------------------------ vicon_position_control
@pytest.mark.parametrize(
    "yaw, error, expected",
    [
        (0, (1000, 0), (0, 1000)),  # facing +x, target ahead
        (0, (0, -1000), (1000, 0)),  # facing +x, target at -y = on the right
        (90, (0, 1000), (0, 1000)),  # facing +y, target ahead
        (90, (1000, 0), (1000, 0)),  # facing +y, +x is on the right
        (180, (1000, 0), (0, -1000)),  # facing -x, target behind
    ],
)
def test_world_to_body(yaw, error, expected):
    right, forward = vicon.world_to_body(*error, yaw)
    assert (round(right), round(forward)) == expected


def test_vicon_rc():
    pose_now = {"x": 0, "y": 0, "z": 800, "yaw": 0}
    rc = vicon.rc_to_target(pose_now, {"x": 100, "y": 0, "z": 1000, "yaw": 20})
    assert rc["y"] > 0 and rc["x"] == 0 and rc["z"] > 0
    assert rc["yaw"] < 0  # target yaw is counter-clockwise -> rc yaw (clockwise positive) negative
    far = vicon.rc_to_target(pose_now, {"x": 5000, "y": 0, "z": 800})
    assert far["y"] == vicon.Gains().max_rc
    assert vicon.rc_to_target(pose_now, {"x": 10, "y": 10, "z": 810}) == {"x": 0.0, "y": 0.0, "z": 0.0, "yaw": 0.0}  # deadband


def test_wrap():
    assert vicon.wrap_deg(190) == -170 and vicon.wrap_deg(-190) == 170
    assert vicon.distance_mm({"x": 0, "y": 0, "z": 0}, {"x": 300, "y": 400, "z": 0}) == 500


# ------------------------------------------------------------ edu_pad_pose_orbit
def test_pose_matrix_and_multiply():
    m = pose.pose_matrix(1, 2, 90)
    assert [[round(v, 9) for v in row] for row in m] == [[0, -1, 1], [1, 0, 2], [0, 0, 1]]
    assert pose.multiply_matrix(pose.pose_matrix(0, 0, 0), pose.pose_matrix(3, 4, 0)) == pose.pose_matrix(3, 4, 0)
    with pytest.raises(ValueError):
        pose.multiply_matrix([[1, 2]], [[1, 2]])


def _rounded(p):
    return tuple(round(v, 6) for v in p)


def test_tello_reading_to_standard():
    # Tello: y right of the rocket, yaw clockwise  ->  standard: y left, yaw counter-clockwise
    assert _rounded(pose.tello_to_standard({"x": 10, "y": 20, "yaw": 30})) == (10, -20, -30)
    assert pose.tello_to_standard({"x": 1, "y": 1}) is None


@pytest.mark.parametrize(
    "pad, reading, expected",
    [
        ((0, 0, 0), {"x": 10, "y": 0, "yaw": 0}, (10, 0, 0)),  # pad = world: 10 cm along the rocket
        ((0, 0, 0), {"x": 0, "y": -30, "yaw": 0}, (0, 30, 0)),  # Tello y -30 = 30 cm LEFT = world +y
        ((100, 0, 90), {"x": 10, "y": 0, "yaw": 0}, (100, 10, 90)),  # rocket along world +y
        ((100, 0, 90), {"x": 0, "y": 0, "yaw": 90}, (100, 0, 0)),  # nose 90 clockwise from the rocket = world +x
        ((50, -60, -90), {"x": 20, "y": 10, "yaw": -45}, (40, -80, -45)),  # rocket along world -y
    ],
)
def test_world_pose(pad, reading, expected):
    assert _rounded(pose.world_pose(pad, reading)) == expected


def test_world_pose_is_consistent_for_two_pads():
    """One drone pose seen from two different pads must give the same world pose."""
    drone = (30.0, 40.0, 20.0)  # world, standard
    readings = []
    for pad in ((0, 0, 0), (100, 50, 135)):
        # what the Tello would report over this pad: drone in the pad frame, in Tello signs
        pad_T = pose.pose_matrix(*pad)
        inv = [[pad_T[0][0], pad_T[1][0], 0], [pad_T[0][1], pad_T[1][1], 0], [0, 0, 1]]
        rel = pose.multiply_matrix(inv, pose.pose_matrix(drone[0] - pad[0], drone[1] - pad[1], drone[2]))
        x, y, yaw = pose.matrix_to_pose(rel)
        readings.append((pad, {"x": x, "y": -y, "yaw": -yaw}))
    for pad, reading in readings:
        assert _rounded(pose.world_pose(pad, reading)) == _rounded(drone)


# ------------------------------------------------------------ talent examples / command test
def _main(name):
    import sys

    module = load_helper(MORE / name / "commander/main.py", f"_t_{name}")
    sys.modules.pop(f"_t_{name}", None)
    return module


def test_battery_pattern():
    m = _main("talent_cooling_battery_gauge")
    full, half, low = m.battery_pattern(100), m.battery_pattern(50), m.battery_pattern(10)
    assert len(full) == 64 and full.count("b") == 8
    assert half.count("b") == 4 and half[:32].count("b") == 0  # filled from the bottom
    assert low.count("r") == 1  # red when low, at least one LED
    assert m.battery_pattern(0).count("0") == 64


def test_ruler_text():
    m = _main("talent_tof_ruler")
    assert m.ruler_text(123.4) == "123cm" and m.ruler_text(819.2) == "--"


def test_command_test_skips_what_the_model_cannot():
    import json

    m = _main("tello_command_test")
    commands = json.loads((MORE.parent / "core/drone/implementations/DJI/tello/commands.json").read_text())
    ok, skipped = m.runnable_steps(m.GROUND_STEPS, commands, "tello")
    skipped_names = {a for a, _ in skipped}
    assert "ext_led" in skipped_names and "get_sdk_version" in skipped_names and "get_battery" not in skipped_names
    ok, skipped = m.runnable_steps(m.GROUND_STEPS, commands, None)
    assert not skipped


def test_vicon_text():
    m = _main("vicon_yolo")
    assert "OCCLUDED" in m.vicon_text({"occluded": True, "subject": "t"})["VICON"]
    block = m.vicon_text({"occluded": False, "subject": "t", "x": 1, "y": 2, "z": 3, "roll": 0, "pitch": 0, "yaw": math.pi, "frame": 5})
    assert block["frame"] == 5
