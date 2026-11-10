"""TelloDrone against a fake Tello over real UDP (tests/conftest.py)."""

import asyncio

import pytest
from conftest import tello_kwargs

from core.bus import get_bus
from core.drone import DroneType, get_drone
from core.drone.implementations.DJI.tello.tello import normalize_model


def run(coro):
    return asyncio.run(coro)


async def _session(fake, actions, wait=0.0, **extra):
    """Publish actions on cmd.t, return all bus events."""
    bus = get_bus()
    events = []
    bus.subscribe("*", lambda t, d: events.append((t, d)))
    drone = get_drone(DroneType.DJI_TELLO, "t", bus=bus, **tello_kwargs(fake, **extra))
    try:
        for action, args in actions:
            await bus.publish("cmd.t", {"action": action, "args": args})
        await asyncio.sleep(wait)
    finally:
        if drone.con_state.value == "connected":
            await drone.disconnect()
        drone.detach()
    return drone, events


def test_connect_takeoff_land(fake_tello):
    drone, events = run(_session(fake_tello, [("connect", {}), ("set_arm", {}), ("takeoff", {}), ("land", {})]))
    assert fake_tello.got[0] == "command"
    assert "takeoff" in fake_tello.got and "land" in fake_tello.got
    assert ("ack.t", {"cmd": "takeoff", "ack": "True"}) in events


def test_custom_ports_are_sent_on_connect(fake_tello):
    run(_session(fake_tello, [("connect", {})]))
    assert any(m.startswith("port ") for m in fake_tello.got)


def test_state_is_unified(fake_tello):
    _, events = run(_session(fake_tello, [("connect", {}), ("start_state_receiver", {})], wait=0.3))
    states = [d for t, d in events if t == "state.t"]
    assert states, "no state received"
    s = states[-1]
    assert s["battery"] == 87 and s["height"] == 80 and s["temperature"] == 63 and s["temperature_low"] == 60
    assert s["attitude"] == {"pitch": 1, "roll": 2, "yaw": 90}
    assert s["mission_pad"] == {"id": 4, "x": 10, "y": 20, "z": 80, "mpry": [0, 30, 0], "yaw": 30}
    assert set(s["position"]) == {"x", "y", "z"}
    assert "bat" not in s and "h" not in s  # raw names are gone


@pytest.mark.parametrize(
    "action, key, value",
    [
        ("get_battery", "battery", 87),
        ("get_height", "height", 100),
        ("get_temperature", "temperature", 63),
        ("get_tof", "tof", 10),
        ("get_attitude", "attitude", {"pitch": 1, "roll": 2, "yaw": 3}),
        ("get_flight_time", "flight_time", 12),
        ("get_acceleration", "acceleration", {"x": 1, "y": 2, "z": -1000}),
    ],
)
def test_get_answers_use_unified_units(fake_tello, action, key, value):
    _, events = run(_session(fake_tello, [("connect", {}), (action, {})]))
    data = [d for t, d in events if t == "data.t"]
    assert data and data[-1][key] == value


def test_basic_model_blocks_edu_commands(fake_tello):
    _, events = run(_session(fake_tello, [("connect", {}), ("set_mission_pad_on", {}), ("ext_led", {})], model="tello"))
    errors = [d for t, d in events if t == "error.t"]
    assert [e["error"] for e in errors] == ["NotSupported", "NotSupported"]
    assert "mon" not in fake_tello.got and not any(m.startswith("EXT") for m in fake_tello.got)


def test_edu_allows_pads_but_not_expansion_kit(fake_tello):
    _, events = run(_session(fake_tello, [("connect", {}), ("set_mission_pad_on", {}), ("ext_led", {})], model="edu"))
    assert "mon" in fake_tello.got
    assert [d["error"] for t, d in events if t == "error.t"] == ["NotSupported"]


def test_talent_allows_everything(fake_tello):
    _, events = run(_session(fake_tello, [("connect", {}), ("ext_led", {})], model="tello_talent"))
    assert any(m.startswith("EXT led") for m in fake_tello.got)
    assert not [d for t, d in events if t == "error.t"]


def test_model_names():
    assert normalize_model(None) is None
    assert normalize_model("EDU") == "tello_edu"
    assert normalize_model("RMTT") == "tello_talent"
    assert normalize_model("basic") == "tello"
    with pytest.raises(ValueError):
        normalize_model("mavic")


def test_stop_is_sent_while_a_move_is_running(fake_tello):
    async def scenario():
        bus = get_bus()
        drone = get_drone(DroneType.DJI_TELLO, "t", bus=bus, **tello_kwargs(fake_tello))
        for action in ("connect", "set_arm", "takeoff"):
            await bus.publish("cmd.t", {"action": action})
        fake_tello.move_delay = 1.0  # the move takes 1 s ...
        move = asyncio.create_task(bus.publish("cmd.t", {"action": "steps_move_forward"}))
        await asyncio.sleep(0.1)
        await bus.publish("cmd.t", {"action": "stop"})  # ... stop must not wait for it
        await asyncio.sleep(0.1)
        result = ("stop" in fake_tello.got, move.done())
        await move
        await drone.disconnect()
        drone.detach()
        return result

    stop_sent, move_finished = run(scenario())
    assert stop_sent and not move_finished


def test_reconnect_after_disconnect(fake_tello):
    """The command port must be free again after disconnect (was a bug)."""

    async def scenario():
        bus = get_bus()
        kwargs = tello_kwargs(fake_tello)
        for _ in range(2):
            drone = get_drone(DroneType.DJI_TELLO, "t", bus=bus, **kwargs)
            await drone.connect()
            assert drone.con_state.value == "connected"
            await drone.disconnect()
            drone.detach()

    run(scenario())


def test_position_estimate_follows_heading(fake_tello):
    async def scenario():
        bus = get_bus()
        drone = get_drone(DroneType.DJI_TELLO, "t", bus=bus, **tello_kwargs(fake_tello))
        for action, args in [
            ("connect", {}),
            ("set_arm", {}),
            ("takeoff", {}),
            ("steps_move_forward", {"distance": 100}),
            ("rotate_cw", {"degrees": 90}),
            ("steps_move_forward", {"distance": 50}),
            ("goto", {"x": 0, "y": 30, "z": 0}),
        ]:
            await bus.publish("cmd.t", {"action": action, "args": args})
        pos = drone.sdk.get_position()
        await drone.disconnect()
        drone.detach()
        return pos

    pos = run(scenario())
    # forward 100 (north), turn right, forward 50 (east), go y=+30 = 30 to the LEFT of the nose (= north)
    assert round(pos["x"]) == 50 and round(pos["y"]) == 130


def test_no_answer_reports_checklist():
    async def scenario():
        bus = get_bus()
        events = []
        bus.subscribe("ack.t", lambda t, d: events.append(d))
        drone = get_drone(DroneType.DJI_TELLO, "t", bus=bus, ip="127.0.0.1", cmd_port=9, cmd_pc_port=0)
        orig = asyncio.wait_for

        async def fast(aw, timeout):  # don't wait 10 s
            return await orig(aw, min(timeout, 0.3))

        asyncio.wait_for = fast
        try:
            await drone.connect()
        finally:
            asyncio.wait_for = orig
        await drone.disconnect()
        drone.detach()
        return events

    events = run(scenario())
    assert events[0]["ack"] == "None" and "firewall" in events[0]["info"]
