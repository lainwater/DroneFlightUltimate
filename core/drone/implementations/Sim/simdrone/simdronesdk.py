import asyncio
from dataclasses import dataclass
from enum import Enum

from core.drone.position_and_attitude import Attitude, Position

_MOVEMENT_MAP = {
    "forward": ("y", +1),
    "backward": ("y", -1),
    "left": ("x", -1),
    "right": ("x", +1),
    "up": ("z", +1),
    "down": ("z", -1),
}

_ATTITUDE_MAP = {
    "forward": ("pitch", -1),
    "backward": ("pitch", +1),
    "left": ("roll", -1),
    "right": ("roll", +1),
    "yaw_left": ("yaw", -1),
    "yaw_right": ("yaw", +1),
}

_TILT_DEGREES = 15.0


class _FlightMode(Enum):
    RC = "rc"
    GOTO = "goto"
    STEPS = "steps"
    NONE_SET = "none"


@dataclass
class _DroneStateData:
    bat: int
    temp: int
    pos: Position
    att: Attitude
    mode: _FlightMode


def _requires(*flag_names: str, sentinel=False):
    def deco(fn):
        async def wrapper(self, *args, **kwargs):
            for flag in flag_names:
                if not getattr(self, flag):
                    return sentinel
            return await fn(self, *args, **kwargs)

        return wrapper

    return deco


class SimDroneSDK:
    def __init__(self, run_cycles_limit: int = 5000, wait_time: float = 0.1):
        self._run_cycles_limit: int = run_cycles_limit
        self._wait_time: int = wait_time

        self._is_connected: bool = False
        self._is_armed: bool = False
        self._is_ready_to_recv: bool = False
        self._is_in_air: bool = False
        self._is_state_gen_running: bool = False
        self._is_landed: bool = True
        self._flight_mode: _FlightMode = _FlightMode.NONE_SET

        self._rc_speed: float = 1.0
        self._takeoff_height: float = 50.0

        self._pos: Position = Position(x=0.0, y=0.0, z=0.0, vx=0.0, vy=0.0, vz=0.0, timestamp=None)
        self._att: Attitude = Attitude(pitch=0.0, roll=0.0, yaw=0.0, vpitch=0.0, vroll=0.0, vyaw=0.0, timestamp=None)
        self._ip: str | None = "67.67.0.1"
        self._port: str | None = "6767"
        self._bat: int = 85
        self._temp: int = 40
        self._state_data = _DroneStateData(bat=self._bat, temp=self._temp, pos=self._pos, att=self._att, mode=self._flight_mode)

    # BASIC METHODS
    async def connect(self, ip: str, port: str) -> bool:
        if (ip == self._ip) and (port == self._port):
            self._ip = ip
            self._port = port
            self._is_ready_to_recv = False
            await asyncio.sleep(self._wait_time)
            self._is_connected = True
            self._is_ready_to_recv = True
            return True
        else:
            return False

    async def disconnect(self) -> bool:
        if self._is_in_air:
            await self.land()
        await asyncio.sleep(self._wait_time)
        self._is_connected = False
        self._is_ready_to_recv = False
        self._pos.x = self._pos.y = self._pos.z = self._pos.vx = self._pos.vy = self._pos.vz = 0.0
        self._att.roll = self._att.pitch = self._att.yaw = self._att.vpitch = self._att.vroll = self._att.vyaw = 0.0
        return True

    @_requires("_is_connected", "_is_ready_to_recv", "_is_landed")
    async def arm(self) -> bool:
        self._is_ready_to_recv = False
        await asyncio.sleep(self._wait_time)
        self._is_armed = True
        self._is_ready_to_recv = True
        return True

    @_requires("_is_connected", "_is_ready_to_recv", "_is_landed")
    async def disarm(self) -> bool:
        self._is_ready_to_recv = False
        await asyncio.sleep(self._wait_time)
        self._is_armed = False
        self._is_ready_to_recv = True
        return True

    # SET METHODS:
    @_requires("_is_connected", "_is_ready_to_recv")
    async def set_flight_mode(self, flight_mode: str) -> bool:
        try:
            new_mode = _FlightMode(flight_mode)
        except ValueError:
            return False
        self._is_ready_to_recv = False
        await asyncio.sleep(self._wait_time)
        self._flight_mode = new_mode
        self._is_ready_to_recv = True
        return True

    @_requires("_is_connected", "_is_ready_to_recv")
    async def set_rc_speed(self, speed: float) -> bool:
        self._rc_speed = speed
        return True

    @_requires("_is_connected", "_is_ready_to_recv")
    async def set_takeoff_height(self, height: float) -> bool:
        self._takeoff_height = height
        return True

    @_requires("_is_connected", "_is_ready_to_recv")
    async def set_ip_and_port(self, ip: str | None = None, port: str | None = None) -> bool:
        if ip is not None:
            self._ip = ip
        if port is not None:
            self._port = port
        await self.disconnect()
        return True

    # GET METHODS
    @_requires("_is_connected", "_is_ready_to_recv", sentinel=None)
    async def get_armed_status(self) -> bool | None:
        return self._is_armed

    @_requires("_is_connected", "_is_ready_to_recv", sentinel=None)
    async def get_state_gen_status(self) -> bool | None:
        return self._is_state_gen_running

    @_requires("_is_connected", "_is_ready_to_recv", sentinel=None)
    async def get_flight_mode(self) -> bool | None:
        return self._flight_mode

    @_requires("_is_connected", "_is_ready_to_recv", sentinel=None)
    async def get_ip_and_port(self) -> tuple | None:
        return self._ip, self._port

    @_requires("_is_connected", "_is_ready_to_recv", sentinel=None)
    async def get_rc_speed(self) -> float | None:
        return self._rc_speed

    @_requires("_is_connected", "_is_ready_to_recv", sentinel=None)
    async def get_takeoff_height(self) -> float | None:
        return self._takeoff_height

    @_requires("_is_connected", "_is_ready_to_recv", sentinel=None)
    async def get_position(self) -> Position | None:
        return self._pos.copy()

    @_requires("_is_connected", "_is_ready_to_recv", sentinel=None)
    async def get_attitude(self) -> Attitude | None:
        return self._att.copy()

    @_requires("_is_connected", "_is_ready_to_recv", sentinel=None)
    async def get_battery(self) -> int | None:
        return self._bat

    @_requires("_is_connected", "_is_ready_to_recv", sentinel=None)
    async def get_temperature(self) -> int | None:
        return self._temp

    # MOVE METHODS
    @_requires("_is_connected")
    async def emergency(self) -> bool:
        if not self._is_connected:
            return False
        self._pos.z = 0
        self._att.pitch = 0
        self._att.roll = 0
        self._is_landed = True
        self._is_in_air = False
        await self.disarm()
        return True

    @_requires("_is_connected", "_is_ready_to_recv", "_is_armed", "_is_landed")
    async def takeoff(self) -> bool:
        if self._is_in_air:
            return False
        self._is_ready_to_recv = False
        await asyncio.sleep(self._wait_time)
        self._is_in_air = True
        self._is_landed = False
        self._pos.z += self._takeoff_height
        self._is_ready_to_recv = True
        return True

    @_requires("_is_connected", "_is_ready_to_recv", "_is_armed", "_is_in_air")
    async def land(self) -> bool:
        if self._is_landed:
            return False
        self._is_ready_to_recv = False
        await asyncio.sleep(self._wait_time)
        self._pos.z = 0
        self._att.pitch = 0
        self._att.roll = 0
        self._is_landed = True
        self._is_in_air = False
        self._is_ready_to_recv = True
        return True

    @_requires("_is_connected", "_is_ready_to_recv", "_is_armed", "_is_in_air")
    async def move_step(self, direction: str, distance: float) -> bool:
        if self._is_landed:
            return False
        if self._flight_mode != _FlightMode.STEPS:
            return False
        axis = _MOVEMENT_MAP[direction][0]
        att_axis = _ATTITUDE_MAP[direction][0]
        sign = _MOVEMENT_MAP[direction][1]
        att_sign = _ATTITUDE_MAP[direction][1]
        setattr(self._pos, axis, getattr(self._pos, axis) + sign * distance)
        setattr(self._att, att_axis, att_sign * _TILT_DEGREES)
        await asyncio.sleep(self._wait_time)

        setattr(self._att, att_axis, 0)
        return True

    @_requires("_is_connected", "_is_ready_to_recv", "_is_armed", "_is_in_air")
    async def goto_pos(self, x: float, y: float, z: float) -> bool:
        if self._is_landed:
            return False
        if self._flight_mode != _FlightMode.GOTO:
            return False
        await asyncio.sleep(self._wait_time)
        self._pos.x = x
        self._pos.y = y
        self._pos.z = z
        return True

    @_requires("_is_connected", "_is_ready_to_recv", "_is_armed", "_is_in_air")
    async def rc(self, x: int, y: int, z: int, yaw: int) -> bool:
        if self._is_landed:
            return False
        if self._flight_mode != _FlightMode.RC:
            return False
        # x = self._normalize_rc(x)
        # y = self._normalize_rc(y)
        # z = self._normalize_rc(z)
        # yaw = self._normalize_rc(yaw)
        # x / l-r dir
        self._att.roll = x * _TILT_DEGREES
        self._pos.x += x * self._rc_speed
        # y / fw-bw dir
        self._att.pitch = y * _TILT_DEGREES
        self._pos.y += y * self._rc_speed
        # z / h dir
        self._pos.z += z * self._rc_speed
        # yaw
        self._att.yaw += yaw * self._rc_speed
        return True

    # Other Stuff
    async def state_stream(self):
        self._is_state_gen_running = True
        try:
            i = 0
            while self._is_connected and i < self._run_cycles_limit and self._is_state_gen_running:
                self._is_state_gen_running = True
                i += 1
                await asyncio.sleep(0.1)
                self._state_data.bat = self._bat
                self._state_data.temp = self._temp
                self._state_data.mode = self._flight_mode
                self._state_data.att = self._att.copy()
                self._state_data.pos = self._pos.copy()
                yield {
                    "battery": self._state_data.bat,
                    "temperature": self._state_data.temp,
                    "flight_mode": self._state_data.mode,
                    "attitude": self._state_data.att.copy(),
                    "position": self._state_data.pos.copy(),
                }
        finally:
            self._is_state_gen_running = False
            return
