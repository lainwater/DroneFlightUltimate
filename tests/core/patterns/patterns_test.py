"""core.patterns - flown on the simdrone, which moves relative to its nose like a real drone."""

import asyncio
import math

import pytest

from core.bus import get_bus
from core.drone import DroneType, get_drone
from core.patterns import PatternAborted, get_patterns, orbit_rc, polygon_edges, split_go


@pytest.mark.parametrize("sides", [3, 4, 5, 6, 12])
def test_polygon_closes(sides):
    edges = polygon_edges(sides, 100)
    assert abs(sum(x for x, _ in edges)) < 1 and abs(sum(y for _, y in edges)) < 1
    assert edges[0] == (100, 0)  # first edge straight ahead
    assert all(abs(math.hypot(x, y) - 100) < 0.2 for x, y in edges)


def test_clockwise_turns_right():
    assert polygon_edges(4, 100, clockwise=True)[1] == (0, -100)  # y is LEFT -> right = negative
    assert polygon_edges(4, 100, clockwise=False)[1] == (0, 100)


def test_split_go():
    assert split_go(1200, 0) == [(400, 0, 0)] * 3
    assert split_go(30, 10, 0) == [(30, 10, 0)]
    with pytest.raises(ValueError):
        split_go(10, 15, 5)  # all axes within 20 cm: the Tello refuses


def test_orbit_rc():
    lr, yaw, seconds = orbit_rc(radius_cm=100, speed_cms=20)
    assert lr == -0.2 and yaw > 0 and seconds == pytest.approx(2 * math.pi * 100 / 20)
    lr2, yaw2, _ = orbit_rc(radius_cm=100, speed_cms=20, clockwise=False)
    assert lr2 == 0.2 and yaw2 == -yaw


class Sim:
    """A flying simdrone + patterns on one bus."""

    async def __aenter__(self):
        self.bus = get_bus()
        self.cmds = []
        self.status = []
        self.bus.subscribe("cmd.s", lambda t, d: self.cmds.append(d))
        self.bus.subscribe("ack.patterns.s", lambda t, d: self.status.append(d["status"]))
        self.drone = get_drone(DroneType.SIM_SIMDRONE, "s", bus=self.bus)
        self.drone.sdk._wait_time = 0.0
        for action in ("connect", "set_arm", "takeoff"):
            await self.bus.publish("cmd.s", {"action": action})
        self.p = get_patterns("s", self.bus, rc_rate_hz=50)
        return self

    def pos(self):
        sdk = self.drone.sdk
        return round(sdk._pos.x, 1), round(sdk._pos.y, 1), round(sdk._att.yaw, 1)

    async def __aexit__(self, *exc):
        self.p.detach()
        await self.drone.disconnect()
        self.drone.detach()


@pytest.mark.parametrize(
    "call",
    [
        lambda p: p.square(100),
        lambda p: p.triangle(100),
        lambda p: p.hexagon(60),
        lambda p: p.circle(80),
        lambda p: p.rectangle(150, 80),
        lambda p: p.waypoints([(100, 0, 0), (100, 100, 30), (0, 0, 0)]),
        lambda p: p.spin(360),
    ],
)
def test_closed_patterns_return_to_start(call):
    async def scenario():
        async with Sim() as s:
            await call(s.p)
            return s.pos()

    x, y, yaw = asyncio.run(scenario())
    assert abs(x) < 1 and abs(y) < 1 and yaw == 0


def test_lawnmower_zigzags():
    async def scenario():
        async with Sim() as s:
            await s.p.lawnmower(lane_length_cm=150, lane_spacing_cm=40, lanes=4)
            return s.pos()

    assert asyncio.run(scenario()) == (-120.0, 0.0, -180.0)  # 3 steps left, ends at the start line facing back


def test_lawnmower_without_turning():
    async def scenario():
        async with Sim() as s:
            await s.p.lawnmower(lane_length_cm=150, lane_spacing_cm=40, lanes=3, shift_right=True, turn=False)
            return s.pos()

    assert asyncio.run(scenario()) == (80.0, 150.0, 0.0)


def test_commands_are_tagged_and_go_over_the_bus():
    async def scenario():
        async with Sim() as s:
            await s.p.square(100)
            return [c for c in s.cmds if c.get("source") == "patterns"]

    cmds = asyncio.run(scenario())
    assert [c["action"] for c in cmds] == ["goto"] * 4


def test_aborts_when_not_flying():
    async def scenario():
        bus = get_bus()
        get_drone(DroneType.SIM_SIMDRONE, "s", bus=bus)
        p = get_patterns("s", bus)
        with pytest.raises(PatternAborted):
            await p.square(100)

    asyncio.run(scenario())


def test_background_start_cancel_and_busy():
    async def scenario():
        async with Sim() as s:
            task = s.p.start(s.p.hover(5))
            await asyncio.sleep(0.1)
            second = s.p.start(s.p.dance())  # busy -> refused
            await s.p.cancel()
            return task.cancelled(), second, s.p.busy, s.status, s.cmds[-1]

    cancelled, second, busy, status, last = asyncio.run(scenario())
    assert cancelled and second is None and not busy
    assert status == ["started", "cancelled"]
    assert last == {"action": "stop", "source": "patterns"}


def test_background_abort_is_reported():
    async def scenario():
        async with Sim() as s:
            await s.bus.publish("cmd.s", {"action": "land"})
            task = s.p.start(s.p.square(100))
            await task
            return s.status

    assert asyncio.run(scenario()) == ["started", "aborted"]


def test_orbit_and_dance_send_rc():
    async def scenario():
        async with Sim() as s:
            await s.p.orbit(radius_cm=100, speed_cms=200)  # fast: ~3 s -> keep the test short
            n_orbit = sum(c["action"] == "rc" for c in s.cmds)
            return n_orbit, s.cmds[-1]

    n, last = asyncio.run(scenario())
    assert n > 10 and last["args"] == {"x": 0, "y": 0, "z": 0, "yaw": 0}
