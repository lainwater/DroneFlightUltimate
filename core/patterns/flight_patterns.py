"""
FlightPatterns - predefined flight patterns, flown by publishing normal drone
commands on the bus (cmd.<drone_id>). Works with every drone that has the
standard commands (Tello, simdrone) and every move ends up in the flight log.

    patterns = get_patterns("drone1", bus)
    await patterns.square(side_cm=100)               # wait until done
    patterns.start(patterns.orbit(radius_cm=100))    # or run in the background ...
    await patterns.cancel()                          # ... and stop it (drone hovers)

The drone must be flying (takeoff first). A pattern stops with PatternAborted
as soon as the drone reports an error (not in air any more, Tello said
'error', ...). Only one background pattern runs at a time.

Frames
    distance patterns use 'goto' = the Tello 'go' frame: x forward, y LEFT, z up (cm),
    relative to where the drone is and how it is turned when the move starts.
    rc patterns use the rc frame: x right, y forward, z up, yaw clockwise, -1..1.

Every command carries "source": "patterns", so a project can tell them from keyboard commands.
Status on the bus: ack.patterns.<drone_id> {"pattern", "status": started | done | cancelled | aborted, "info"?}
"""

import asyncio
import math
from typing import Awaitable, Iterable

GO_MIN_CM = 20  # Tello 'go': x, y, z must not ALL be within -20..20
GO_MAX_CM = 500  # and none beyond +-500
RC_RATE_HZ = 10  # rc commands per second during rc patterns
KEEPALIVE_S = 1.0  # Tello lands by itself after 15 s without any command


class PatternAborted(Exception):
    """The drone reported an error (or the pattern was impossible) - pattern stopped."""


def polygon_edges(sides: int, side_cm: float, clockwise: bool = True) -> list[tuple[float, float]]:
    """Relative (x forward, y left) moves of a regular polygon, first edge straight ahead.
    The drone does not turn; the sum of all edges is (0, 0)."""
    if sides < 3:
        raise ValueError("a polygon needs at least 3 sides")
    sign = -1 if clockwise else 1  # clockwise (seen from above) = turning right = towards -y
    edges = []
    for k in range(sides):
        heading = sign * 2 * math.pi * k / sides
        edges.append((round(side_cm * math.cos(heading), 1), round(side_cm * math.sin(heading), 1)))
    return edges


def split_go(x: float, y: float, z: float = 0.0) -> list[tuple[int, int, int]]:
    """One relative move -> Tello-valid 'go' steps (each axis within +-500, not all within +-20)."""
    longest = max(abs(x), abs(y), abs(z))
    if longest < GO_MIN_CM:
        raise ValueError(f"move ({x:.0f}, {y:.0f}, {z:.0f}) cm is too short: one axis must be at least {GO_MIN_CM} cm")
    parts = math.ceil(longest / GO_MAX_CM)
    return [(round(x / parts), round(y / parts), round(z / parts))] * parts


class FlightPatterns:
    def __init__(self, drone_id: str, bus: object, rc_rate_hz: float = RC_RATE_HZ):
        self.drone_id = drone_id
        self.bus = bus
        self.rc_rate_hz = rc_rate_hz
        self._task: asyncio.Task | None = None
        self._failure: str | None = None
        self.bus.subscribe(f"error.{drone_id}", self._on_error)
        self.bus.subscribe(f"ack.{drone_id}", self._on_ack)

    def detach(self) -> None:
        self.bus.unsubscribe(f"error.{self.drone_id}", self._on_error)
        self.bus.unsubscribe(f"ack.{self.drone_id}", self._on_ack)

    # ------------------------------------------------------------ bus
    async def _on_error(self, topic: str, data) -> None:
        self._failure = str(data.get("message") or data.get("error") or data) if isinstance(data, dict) else str(data)

    async def _on_ack(self, topic: str, data) -> None:
        if isinstance(data, dict) and data.get("ack") == "False":
            self._failure = f"drone refused '{data.get('cmd')}'"

    async def send(self, action: str, args: dict | None = None) -> None:
        """One drone command; returns when the drone has answered.
        Raises PatternAborted if the drone reported an error meanwhile."""
        self._failure = None
        await self.bus.publish(f"cmd.{self.drone_id}", {"action": action, "args": args or {}, "source": "patterns"})
        if self._failure:
            raise PatternAborted(f"{action}: {self._failure}")

    async def _status(self, pattern: str, status: str, info: str | None = None) -> None:
        data = {"pattern": pattern, "status": status}
        if info:
            data["info"] = info
        await self.bus.publish(f"ack.patterns.{self.drone_id}", data)

    # ------------------------------------------------------------ background control
    @property
    def busy(self) -> bool:
        return self._task is not None and not self._task.done()

    def start(self, pattern: Awaitable) -> asyncio.Task | None:
        """Run a pattern in the background (bus handlers return at once).
        Returns None (and does nothing) if one is already running."""
        if self.busy:
            if hasattr(pattern, "close"):
                pattern.close()  # never started - no "coroutine was never awaited" warning
            return None
        self._task = asyncio.create_task(self._run(pattern))
        return self._task

    async def _run(self, pattern) -> None:
        name = getattr(pattern, "__name__", "pattern")
        await self._status(name, "started")
        try:
            await pattern
        except asyncio.CancelledError:
            await self._status(name, "cancelled")
            raise
        except (PatternAborted, ValueError) as e:
            await self._status(name, "aborted", str(e))
            return
        await self._status(name, "done")

    async def cancel(self) -> None:
        """Stop the background pattern; the drone stops and hovers."""
        if self.busy:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            # 'stop' interrupts a running go/move on the Tello at once
            await self.bus.publish(f"cmd.{self.drone_id}", {"action": "stop", "source": "patterns"})
        self._task = None

    # ------------------------------------------------------------ building blocks
    async def rc_for(self, x: float = 0.0, y: float = 0.0, z: float = 0.0, yaw: float = 0.0, seconds: float = 0.5) -> None:
        """Send the same rc command at rc_rate_hz for `seconds` (fixed rate, no drift)."""
        loop = asyncio.get_running_loop()
        t_end = loop.time() + seconds
        next_tick = loop.time()
        try:
            while loop.time() < t_end:
                await self.send("rc", {"x": x, "y": y, "z": z, "yaw": yaw})
                next_tick += 1.0 / self.rc_rate_hz
                await asyncio.sleep(max(0.0, min(next_tick, t_end) - loop.time()))
        finally:
            if x or y or z or yaw:
                await self.bus.publish(f"cmd.{self.drone_id}", {"action": "rc", "args": {"x": 0, "y": 0, "z": 0, "yaw": 0}, "source": "patterns"})

    async def hover(self, seconds: float) -> None:
        """Hold position; keeps the Tello from auto-landing (it does after 15 s without commands)."""
        loop = asyncio.get_running_loop()
        t_end = loop.time() + seconds
        while loop.time() < t_end:
            await self.send("rc", {"x": 0, "y": 0, "z": 0, "yaw": 0})
            await asyncio.sleep(min(KEEPALIVE_S, max(0.0, t_end - loop.time())))

    async def go(self, x: float, y: float, z: float = 0.0, speed: int = 30) -> None:
        """Relative move (x forward, y left, z up, cm), split into Tello-valid steps."""
        for gx, gy, gz in split_go(x, y, z):
            await self.send("goto", {"x": gx, "y": gy, "z": gz, "speed": int(speed)})

    # ------------------------------------------------------------ distance patterns
    async def polygon(self, sides: int, side_cm: float = 100, speed: int = 30, clockwise: bool = True) -> None:
        """Regular polygon, first edge straight ahead, nose keeps pointing the same way."""
        edges = polygon_edges(sides, side_cm, clockwise)
        for x, y in edges:  # validate everything before flying the first edge
            split_go(x, y)
        for x, y in edges:
            await self.go(x, y, 0, speed)

    async def triangle(self, side_cm: float = 100, speed: int = 30, clockwise: bool = True) -> None:
        await self.polygon(3, side_cm, speed, clockwise)

    async def square(self, side_cm: float = 100, speed: int = 30, clockwise: bool = True) -> None:
        await self.polygon(4, side_cm, speed, clockwise)

    async def hexagon(self, side_cm: float = 60, speed: int = 30, clockwise: bool = True) -> None:
        await self.polygon(6, side_cm, speed, clockwise)

    async def rectangle(self, length_cm: float = 150, width_cm: float = 80, speed: int = 30, clockwise: bool = True) -> None:
        """length straight ahead, width to the right (clockwise) or left."""
        side = -width_cm if clockwise else width_cm
        for x, y in ((length_cm, 0), (0, side), (-length_cm, 0), (0, -side)):
            await self.go(x, y, 0, speed)

    async def circle(self, radius_cm: float = 80, segments: int = 12, speed: int = 30, clockwise: bool = True) -> None:
        """Circle approximated by a polygon (precise, nose fixed). Starts on the circle,
        centre is to the right (clockwise) or left."""
        side = 2 * radius_cm * math.sin(math.pi / segments)
        await self.polygon(segments, side, speed, clockwise)

    async def waypoints(self, points: Iterable[tuple[float, float, float]], speed: int = 30) -> None:
        """Fly through points given RELATIVE to the start (x forward, y left, z up, cm)."""
        cx = cy = cz = 0.0
        for px, py, pz in points:
            await self.go(px - cx, py - cy, pz - cz, speed)
            cx, cy, cz = px, py, pz

    async def lawnmower(
        self, lane_length_cm: float = 150, lane_spacing_cm: float = 40, lanes: int = 4, shift_right: bool = False, turn: bool = True
    ) -> None:
        """Search pattern: lane, step over, lane back, ... With turn=True the drone turns
        180 deg at each lane end so it always flies nose first (camera ahead)."""
        side, other = ("right", "left") if shift_right else ("left", "right")
        for lane in range(lanes):
            back = lane % 2 == 1 and not turn
            await self.send(f"steps_move_{'backward' if back else 'forward'}", {"distance": lane_length_cm})
            if lane == lanes - 1:
                break
            # after a 180 deg turn the same side of the area is on the other hand
            step = side if (lane % 2 == 0 or not turn) else other
            await self.send(f"steps_move_{step}", {"distance": lane_spacing_cm})
            if turn:
                await self.send("rotate_cw", {"degrees": 180})

    async def spin(self, degrees: int = 360, clockwise: bool = True) -> None:
        """Turn on the spot (in steps of at most 360)."""
        action = "rotate_cw" if clockwise else "rotate_ccw"
        left = abs(int(degrees))
        while left > 0:
            step = min(360, left)
            await self.send(action, {"degrees": step})
            left -= step

    # ------------------------------------------------------------ rc patterns
    async def orbit(
        self,
        radius_cm: float = 100,
        speed_cms: float = 20,
        laps: float = 1,
        clockwise: bool = True,
        cms_per_rc: float = 1.0,
        deg_per_s_per_rc: float = 0.35,
        yaw_correction: float = 1.2,
    ) -> None:
        """Circle around a point radius_cm straight ahead, nose pointing at it.
        cms_per_rc / deg_per_s_per_rc: how fast the drone flies / turns per rc
        unit (1 % of full stick) - calibrate them for your drone."""
        lr, yaw, seconds = orbit_rc(radius_cm, speed_cms, laps, clockwise, cms_per_rc, deg_per_s_per_rc, yaw_correction)
        await self.rc_for(x=lr, yaw=yaw, seconds=seconds)

    async def dance(self, amplitude: float = 0.4) -> None:
        """Wiggle, sway, bob, nod, shake - ends roughly where it started."""
        a = amplitude
        pause = [(0, 0, 0, 0, 0.4)]
        wiggle = [(0, 0, 0, 0.5, 0.35), (0, 0, 0, -0.5, 0.35)] * 3
        sway = [(a, 0, 0, 0, 0.5), (-a, 0, 0, 0, 0.5), (-a, 0, 0, 0, 0.5), (a, 0, 0, 0, 0.5)]
        bob = [(0, 0, a, 0, 0.4), (0, 0, -a, 0, 0.4)] * 2
        nod = [(0, a, 0, 0, 0.4), (0, -a, 0, 0, 0.4)]
        shake = [(0, 0, 0, 0.4, 0.2), (0, 0, 0, -0.4, 0.2)] * 4
        for x, y, z, yaw, seconds in wiggle + pause + sway + pause + bob + pause + nod + pause + wiggle + pause + shake + pause:
            await self.rc_for(x, y, z, yaw, seconds)


def orbit_rc(
    radius_cm: float,
    speed_cms: float,
    laps: float = 1,
    clockwise: bool = True,
    cms_per_rc: float = 1.0,
    deg_per_s_per_rc: float = 0.35,
    yaw_correction: float = 1.2,
) -> tuple[float, float, float]:
    """(sideways rc, yaw rc, seconds) for an orbit. Facing the centre: strafing left
    while yawing right = clockwise seen from above."""
    lr_units = min(100.0, speed_cms / cms_per_rc)
    yaw_units = min(100.0, yaw_correction * math.degrees(speed_cms / radius_cm) / deg_per_s_per_rc)
    sign = 1 if clockwise else -1
    seconds = laps * 2 * math.pi * radius_cm / speed_cms
    return -sign * lr_units / 100.0, sign * yaw_units / 100.0, seconds
