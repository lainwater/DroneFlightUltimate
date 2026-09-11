"""
Tests for core.drone.implementations.Sim.simdrone.SimDrone (and, by
extension, DroneBase's execute()/publish_parser() dispatch machinery).

Run with: pytest tests/core/drone/Sim/simdrone/simdrone_test.py -v

These tests assume the fixes discussed in chat have been applied:
- publish_parser() and every caller of it actually `await` the publish
- execute() dispatches via getattr(self, ...) not getattr(self.sdk, ...)
- parse_bus_event() strips "action" out of kwargs before calling execute()
- commands.json maps "backward" -> "move_backward"
- SimDrone implements stop_state_reciever() and the config_dir property
"""

import asyncio

import pytest

from core.bus import get_bus
from core.drone import DroneType, get_drone
from core.drone.base import DroneConState, DroneFlightState


def make_drone(bus, drone_id: str = "drone1"):
    return get_drone(DroneType.SIM_SIMDRONE, drone_id, bus=bus, ip="127.0.0.1")


def test_connect_command_updates_state_and_publishes_ack():
    bus = get_bus()
    drone = make_drone(bus)
    acks = []
    bus.subscribe("ack.drone1", lambda t, d: acks.append(d))

    asyncio.run(bus.publish("cmd.drone1", {"action": "connect"}))

    assert len(acks) == 1
    assert drone.con_state == DroneConState.CONNECTED


def test_takeoff_then_move_forward_publishes_two_acks():
    bus = get_bus()
    drone = make_drone(bus)
    acks = []
    bus.subscribe("ack.drone1", lambda t, d: acks.append(d))

    async def fly():
        await bus.publish("cmd.drone1", {"action": "takeoff"})
        await bus.publish("cmd.drone1", {"action": "forward", "distance": 50})

    asyncio.run(fly())

    assert len(acks) == 2
    assert drone.flight_state == DroneFlightState.INAIR


def test_move_command_is_ignored_while_still_landed():
    bus = get_bus()
    drone = make_drone(bus)
    acks = []
    bus.subscribe("ack.drone1", lambda t, d: acks.append(d))

    asyncio.run(bus.publish("cmd.drone1", {"action": "forward", "distance": 50}))

    # Guard in move_forward() should have skipped the actual move - the
    # drone never took off, so no ack should have been published.
    assert acks == []
    assert drone.flight_state == DroneFlightState.LANDED


def test_backward_command_reaches_move_backward_method():
    bus = get_bus()
    drone = make_drone(bus)

    async def fly():
        await bus.publish("cmd.drone1", {"action": "takeoff"})
        await bus.publish("cmd.drone1", {"action": "backward", "distance": 20})

    asyncio.run(fly())

    # If commands.json still pointed at the non-existent "move_back",
    # execute() would raise AttributeError instead of reaching this line.
    assert drone.flight_state == DroneFlightState.INAIR


def test_execute_raises_for_unknown_action():
    bus = get_bus()
    drone = make_drone(bus)

    with pytest.raises(ValueError):
        asyncio.run(drone.execute("do_a_barrel_roll"))


def test_parse_bus_event_publishes_error_when_action_key_missing():
    bus = get_bus()
    drone = make_drone(bus)
    errors = []
    bus.subscribe("error.drone1", lambda t, d: errors.append(d))

    # Must NOT raise - a malformed command should surface as an error
    # event, not crash whoever published it.
    asyncio.run(drone.parse_bus_event("cmd.drone1", {"distance": 10}))

    assert len(errors) == 1
    assert errors[0]["error"] == "missing_action"


def test_parse_bus_event_publishes_error_for_unknown_action():
    bus = get_bus()
    make_drone(bus)
    errors = []
    bus.subscribe("error.drone1", lambda t, d: errors.append(d))

    asyncio.run(bus.publish("cmd.drone1", {"action": "do_a_barrel_roll"}))

    assert len(errors) == 1
    assert errors[0]["error"] == "ValueError"
    assert errors[0]["action"] == "do_a_barrel_roll"


def test_parse_bus_event_publishes_error_when_mapped_method_missing():
    bus = get_bus()
    drone = make_drone(bus)
    errors = []
    bus.subscribe("error.drone1", lambda t, d: errors.append(d))

    # Simulate a corrupt/miswritten commands.json entry pointing at a
    # method that doesn't exist on this drone.
    drone.command_map["explode"] = {"method": "self_destruct"}
    asyncio.run(bus.publish("cmd.drone1", {"action": "explode"}))

    assert len(errors) == 1
    assert errors[0]["error"] == "AttributeError"


def test_parse_bus_event_publishes_error_for_missing_required_argument():
    bus = get_bus()
    drone = make_drone(bus)
    errors = []
    bus.subscribe("error.drone1", lambda t, d: errors.append(d))

    async def fly():
        await bus.publish("cmd.drone1", {"action": "takeoff"})
        # "forward" requires a distance kwarg - omit it on purpose.
        await bus.publish("cmd.drone1", {"action": "forward"})

    asyncio.run(fly())

    assert len(errors) == 1
    assert errors[0]["error"] == "TypeError"


def test_get_battery_publishes_data_event():
    bus = get_bus()
    make_drone(bus)
    data_events = []
    bus.subscribe("data.drone1", lambda t, d: data_events.append(d))

    asyncio.run(bus.publish("cmd.drone1", {"action": "get_battery"}))

    assert data_events == [{"battery": 100}]


def test_get_ip_publishes_the_configured_ip_not_gps():
    bus = get_bus()
    make_drone(bus)
    data_events = []
    bus.subscribe("data.drone1", lambda t, d: data_events.append(d))

    asyncio.run(bus.publish("cmd.drone1", {"action": "get_ip"}))

    # Regression test for the copy-paste bug where get_ip() published
    # {"gps": ...} instead of the drone's actual IP.
    assert data_events == [{"ip": "127.0.0.1"}]


def test_get_state_publishes_current_flight_and_connection_state():
    bus = get_bus()
    make_drone(bus)
    state_events = []
    bus.subscribe("state.drone1", lambda t, d: state_events.append(d))

    asyncio.run(bus.publish("cmd.drone1", {"action": "get_state"}))

    assert state_events == [{"flight_state": "landed", "con_state": "disconnected"}]


def test_get_command_map_publishes_full_command_map():
    bus = get_bus()
    make_drone(bus)
    info_events = []
    bus.subscribe("info.drone1", lambda t, d: info_events.append(d))

    asyncio.run(bus.publish("cmd.drone1", {"action": "get_command_map"}))

    assert info_events[0]["forward"]["method"] == "move_forward"


def test_two_drone_instances_on_same_bus_do_not_cross_talk():
    bus = get_bus()
    drone1 = make_drone(bus, drone_id="drone1")
    drone2 = make_drone(bus, drone_id="drone2")

    acks1, acks2 = [], []
    bus.subscribe("ack.drone1", lambda t, d: acks1.append(d))
    bus.subscribe("ack.drone2", lambda t, d: acks2.append(d))

    asyncio.run(bus.publish("cmd.drone1", {"action": "connect"}))

    assert len(acks1) == 1
    assert acks2 == []
    assert drone1.con_state == DroneConState.CONNECTED
    assert drone2.con_state == DroneConState.DISCONNECTED


def test_detach_stops_drone_from_reacting_to_commands():
    bus = get_bus()
    drone = make_drone(bus)
    drone.detach()

    acks = []
    bus.subscribe("ack.drone1", lambda t, d: acks.append(d))
    asyncio.run(bus.publish("cmd.drone1", {"action": "connect"}))

    assert acks == []
    assert drone.con_state == DroneConState.DISCONNECTED


def test_move_helper_works_identically_across_all_directions():
    bus = get_bus()
    drone = make_drone(bus)
    acks = []
    bus.subscribe("ack.drone1", lambda t, d: acks.append(d))

    async def fly():
        await bus.publish("cmd.drone1", {"action": "takeoff"})
        for direction in ("forward", "backward", "up", "down", "left", "right"):
            await bus.publish("cmd.drone1", {"action": direction, "distance": 10})

    asyncio.run(fly())

    # 1 ack for takeoff + 1 per direction
    assert len(acks) == 7
    assert drone.flight_state == DroneFlightState.INAIR


def test_concurrent_move_commands_do_not_overlap():
    """While one discrete move's SDK call is in flight, a second move
    command arriving on the bus must be silently ignored - not queued,
    not overlapped. This mirrors what a real blocking SDK call (e.g.
    djitellopy's move_forward) already forces physically."""
    bus = get_bus()
    drone = make_drone(bus)
    acks = []
    bus.subscribe("ack.drone1", lambda t, d: acks.append(d))

    async def fly():
        await bus.publish("cmd.drone1", {"action": "takeoff"})
        # Fire two moves back-to-back without awaiting the first one's
        # full completion in between.
        await asyncio.gather(
            bus.publish("cmd.drone1", {"action": "forward", "distance": 10}),
            bus.publish("cmd.drone1", {"action": "backward", "distance": 10}),
        )

    asyncio.run(fly())

    # Only the first move to actually start should have gone through -
    # the second one saw flight_state == MOVING and returned early.
    assert len(acks) == 2  # takeoff + exactly one move
    assert drone.flight_state == DroneFlightState.INAIR


def test_stop_state_reciever_without_prior_start_is_a_noop():
    bus = get_bus()
    drone = make_drone(bus)

    # Must not raise even though start_state_reciever() was never called.
    asyncio.run(drone.stop_state_reciever())
    assert drone.data_gen_task is None


def test_stop_state_reciever_actually_cancels_the_background_task():
    bus = get_bus()
    drone = make_drone(bus)
    drone.sdk.data_gen_limit = 1000  # would run "forever" if not cancelled

    async def start_and_stop():
        await bus.publish("cmd.drone1", {"action": "connect"})
        await drone.start_state_reciever()
        task = drone.data_gen_task
        await asyncio.sleep(0.05)
        await drone.stop_state_reciever()
        return task

    task = asyncio.run(start_and_stop())

    assert task.cancelled() or task.done()
    assert drone.data_gen_task is None


def test_state_receiver_streams_battery_and_gps_onto_state_topic():
    bus = get_bus()
    drone = make_drone(bus)
    drone.sdk.data_gen_limit = 3  # keep the test fast
    events = []
    bus.subscribe("state.drone1", lambda t, d: events.append(d))

    async def stream_a_bit():
        await bus.publish("cmd.drone1", {"action": "connect"})  # sets sdk.connected = True
        await bus.publish("cmd.drone1", {"action": "start_state_reciever"})
        await asyncio.sleep(0.35)  # let a couple of 0.1s ticks through
        await drone.stop_state_reciever()

    asyncio.run(stream_a_bit())

    assert len(events) >= 1
    assert "battery" in events[0]
    assert "gps" in events[0]