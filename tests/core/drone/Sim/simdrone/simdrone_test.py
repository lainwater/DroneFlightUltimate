"""SimDrone: flies over the bus without any flight-mode setup, moves relative to its nose."""

import asyncio
import json

import pytest

from core.bus import get_bus
from core.drone import DroneType, get_drone


async def _fly(actions, state_wait=0.0):
    bus = get_bus()
    events = []
    bus.subscribe("*", lambda t, d: events.append((t, d)))
    drone = get_drone(DroneType.SIM_SIMDRONE, "s", bus=bus)
    drone.sdk._wait_time = 0.0
    for action, args in [("connect", {}), ("set_arm", {}), ("takeoff", {})] + actions:
        await bus.publish("cmd.s", {"action": action, "args": args})
    await asyncio.sleep(state_wait)
    pos = (round(drone.sdk._pos.x, 1), round(drone.sdk._pos.y, 1), round(drone.sdk._pos.z, 1), round(drone.sdk._att.yaw, 1))
    await drone.disconnect()
    drone.detach()
    return pos, events


def test_default_kwargs_work():
    get_drone(DroneType.SIM_SIMDRONE, "s", bus=get_bus())  # no ip/port given (was a KeyError)


def test_rc_steps_goto_without_flight_mode():
    pos, events = asyncio.run(
        _fly([("rc", {"x": 0, "y": 1, "z": 0, "yaw": 0}), ("steps_move_forward", {"distance": 50}), ("goto", {"x": 100, "y": 50, "z": 20})])
    )
    assert not [d for t, d in events if t == "error.s"]
    assert pos == (-50.0, 151.0, 70.0, 0.0)  # goto: x forward, y LEFT -> world x -50


def test_moves_are_relative_to_the_nose():
    pos, _ = asyncio.run(_fly([("rotate_cw", {"degrees": 90}), ("steps_move_forward", {"distance": 100}), ("goto", {"x": 0, "y": 40, "z": 0})]))
    assert pos == (100.0, 40.0, 50.0, 90.0)  # facing east: forward = +x, left = +y


@pytest.mark.parametrize("degrees, expected", [(90, 90.0), (270, -90.0), (180, -180.0)])
def test_rotate_wraps(degrees, expected):
    pos, _ = asyncio.run(_fly([("rotate_cw", {"degrees": degrees})]))
    assert pos[3] == expected


def test_unified_json_safe_telemetry():
    _, events = asyncio.run(_fly([("get_position", {}), ("get_attitude", {}), ("start_state_receiver", {})], state_wait=0.25))
    data = [d for t, d in events if t == "data.s"]
    assert data[0] == {"position": {"x": 0.0, "y": 0.0, "z": 50.0}}
    assert set(data[1]["attitude"]) == {"pitch", "roll", "yaw"}
    state = [d for t, d in events if t == "state.s"][-1]
    assert {"battery", "temperature", "height", "attitude", "position", "speed", "flight_mode"} == set(state)
    json.dumps(state)  # recorder needs JSON


def test_stop_and_mission_pad_goto():
    _, events = asyncio.run(_fly([("stop", {}), ("goto", {"x": 50, "y": 0, "z": 0, "mid": "m1"})]))
    assert ("ack.s", {"cmd": "stop", "ack": "sent"}) in events
    assert any(t == "error.s" and d["error"] == "NotSupported" for t, d in events)


def test_commands_need_states():
    async def scenario():
        bus = get_bus()
        errors = []
        bus.subscribe("error.s", lambda t, d: errors.append(d))
        drone = get_drone(DroneType.SIM_SIMDRONE, "s", bus=bus)
        await bus.publish("cmd.s", {"action": "takeoff"})
        drone.detach()
        return errors

    assert "Not connected" in asyncio.run(scenario())[0]["error"]
