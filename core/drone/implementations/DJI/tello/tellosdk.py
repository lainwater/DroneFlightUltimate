"""
TelloSDK - async UDP transport layer for a real DJI/Ryze Tello, per
the official Tello SDK 2.0.

Two things this does differently from a naive blocking-socket wrapper:

1. Uses asyncio's own UDP transport (loop.create_datagram_endpoint),
   never a blocking socket.recvfrom(). A blocking receive with a
   multi-second timeout inside an `async def` would freeze the ENTIRE
   event loop for that whole duration - no video frames, no other bus
   events, nothing else runs meanwhile.

2. Send and receive are separate concerns. send_and_receive() sends a
   command and waits for its response - but if nothing comes back
   within the timeout, that does NOT necessarily mean the command
   failed. The real Tello sometimes drops the ack over UDP while still
   executing the command perfectly. So a timeout returns a THIRD
   result, distinct from True/False: None ("sent, no idea if it
   worked"), instead of collapsing it into a false "failed".
"""

import asyncio
from typing import Any

import cv2 as cv


def _coerce_number(value: str):
    """Most Tello read-command responses are plain numbers; try int,
    then float, then just hand back the raw string unchanged."""
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value


def _parse_state_string(raw: str) -> dict[str, Any]:
    """Tello broadcasts state as 'pitch:0;roll:0;yaw:0;...;\\r\\n' -
    split on ';', then ':', coercing each value to a number where
    possible."""
    state: dict[str, Any] = {}
    for field in raw.strip().rstrip(";").split(";"):
        if ":" not in field:
            continue
        key, _, value = field.partition(":")
        state[key] = _coerce_number(value)
    return state


class _TelloCommandProtocol(asyncio.DatagramProtocol):
    def __init__(self, queue: "asyncio.Queue[str]"):
        self._queue = queue

    def datagram_received(self, data: bytes, addr) -> None:
        self._queue.put_nowait(data.decode("utf-8", errors="replace").strip())


class _TelloStateProtocol(asyncio.DatagramProtocol):
    def __init__(self, queue: "asyncio.Queue[dict]"):
        self._queue = queue

    def datagram_received(self, data: bytes, addr) -> None:
        self._queue.put_nowait(_parse_state_string(data.decode("utf-8", errors="replace")))


_POSITION_DELTA = {
    "forward": ("y", 1),
    "backward": ("y", -1),
    "left": ("x", -1),
    "right": ("x", 1),
    "up": ("z", 1),
    "down": ("z", -1),
}

_RC_CM_PER_SECOND_PER_UNIT = 2.0
_RC_TICK_SECONDS = 0.1


class TelloSDK:
    def __init__(self, ip: str, cmd_port: int, cmd_pc_port: int, state_port: int, video_port: int):
        self.ip = ip
        self.cmd_port = cmd_port
        self.cmd_pc_port = cmd_pc_port
        self.state_port = state_port
        self.video_port = video_port

        self._cmd_transport: asyncio.DatagramTransport | None = None
        self._state_transport: asyncio.DatagramTransport | None = None
        self._response_queue: "asyncio.Queue[str]" = asyncio.Queue()
        self._state_queue: "asyncio.Queue[dict]" = asyncio.Queue()
        self._send_lock = asyncio.Lock()
        self._video_capture: "cv.VideoCapture | None" = None
        self._video_stop = False

        # position estimate - x/y have NO real sensor on
        # a bare Tello (no mission pads)
        # z gets overwritten with the real 'h' field whenever the
        # state stream is running (see TelloDrone._consume_state_stream) -
        # only falls back to dead-reckoning for z when it isn't.
        self.position = {"x": 0.0, "y": 0.0, "z": 0.0}
        self._rc_velocity = {"x": 0.0, "y": 0.0, "z": 0.0}
        self._position_task: asyncio.Task | None = None

    def get_position(self) -> dict:
        return dict(self.position)

    def apply_step_delta(self, direction: str, distance: float) -> None:
        axis_info = _POSITION_DELTA.get(direction)
        if axis_info:
            axis, sign = axis_info
            self.position[axis] += sign * distance

    def apply_goto_delta(self, x: float, y: float, z: float) -> None:
        self.position["x"] += x
        self.position["y"] += y
        self.position["z"] += z

    def track_rc_velocity(self, x: float, y: float, z: float, yaw: float) -> None:
        """Best-effort dead-reckoning while rc is held - starts a
        background integrator that keeps updating position for as
        long as velocity stays non-zero"""
        self._rc_velocity = {"x": x, "y": y, "z": z}
        if self._position_task is None or self._position_task.done():
            self._position_task = asyncio.create_task(self._integrate_position())

    async def _integrate_position(self) -> None:
        while any(abs(v) > 0 for v in self._rc_velocity.values()):
            for axis in ("x", "y", "z"):
                self.position[axis] += self._rc_velocity[axis] * _RC_CM_PER_SECOND_PER_UNIT * _RC_TICK_SECONDS
            await asyncio.sleep(_RC_TICK_SECONDS)

    # ---------------------------------------------------------- connection
    async def open_command_channel(self) -> None:
        loop = asyncio.get_running_loop()
        self._cmd_transport, _ = await loop.create_datagram_endpoint(
            lambda: _TelloCommandProtocol(self._response_queue),
            local_addr=("0.0.0.0", self.cmd_pc_port),
        )

    async def close_command_channel(self) -> None:
        if self._cmd_transport and self._position_task:
            self._cmd_transport.close()
            self._cmd_transport = None
            self._position_task.cancel()
            try:
                await self._position_task
            except asyncio.CancelledError:
                pass
            self._position_task = None

    async def open_state_channel(self) -> None:
        loop = asyncio.get_running_loop()
        self._state_transport, _ = await loop.create_datagram_endpoint(
            lambda: _TelloStateProtocol(self._state_queue),
            local_addr=("0.0.0.0", self.state_port),
        )

    async def close_state_channel(self) -> None:
        if self._state_transport:
            self._state_transport.close()
            self._state_transport = None

    # ---------------------------------------------------------- commands
    def send(self, msg: str) -> None:
        """Fire-and-forget - no response awaited. Used for 'rc', which
        the real Tello SDK never acknowledges."""
        if self._cmd_transport:
            self._cmd_transport.sendto(msg.encode("utf-8"), (self.ip, self.cmd_port))

    async def send_and_receive(self, msg: str, timeout: float = 7.0) -> bool | None:
        """Returns True ('ok'), False ('error' or any other explicit
        rejection), or None (no response within timeout - the command
        may have still succeeded, we just don't know)."""
        async with self._send_lock:
            while not self._response_queue.empty():
                self._response_queue.get_nowait()
            self.send(msg)
            try:
                raw = await asyncio.wait_for(self._response_queue.get(), timeout=timeout)
            except asyncio.TimeoutError:
                return None
            return raw.strip().lower() == "ok"

    async def query(self, msg: str, timeout: float = 7.0) -> str | None:
        """Like send_and_receive, but for '?' read-commands where the
        response is a value, not ok/error. Returns the raw string, or
        None on timeout."""
        async with self._send_lock:
            while not self._response_queue.empty():
                self._response_queue.get_nowait()
            self.send(msg)
            try:
                raw = await asyncio.wait_for(self._response_queue.get(), timeout=timeout)
            except asyncio.TimeoutError:
                return None
            return raw.strip()

    # ---------------------------------------------------------- state stream
    async def state_stream(self):
        """Async generator yielding each parsed state dict as it
        arrives. Matches SimDroneSDK.state_stream()'s interface so
        TelloDrone can reuse the exact same consumption loop as
        SimDrone does."""
        while True:
            state = await self._state_queue.get()
            yield state

    # ---------------------------------------------------------- video stream
    async def open_video_channel(self) -> None:
        """VideoCapture's constructor itself blocks while it probes the
        stream - runs off the event loop, same reasoning as everywhere else here."""
        self._video_stop = False
        self._video_capture = await asyncio.to_thread(cv.VideoCapture, f"udp://0.0.0.0:{self.video_port}")

    def stop_video_stream(self) -> None:
        """Signals video_stream()'s loop to exit on its NEXT iteration.
        Deliberately does NOT release the capture yet - see close_video_channel()."""
        self._video_stop = True

    async def close_video_channel(self) -> None:
        """Only call this after the consumer task has actually finished
        (see TelloDrone.stop_video). asyncio.Task.cancel() can't interrupt
        a blocking call already running in a worker thread - if we release()
        while a cap.read() from the previous iteration is still in flight
        on another thread, that's a real OpenCV crash risk, not just a
        theoretical one."""
        if self._video_capture:
            await asyncio.to_thread(self._video_capture.release)
            self._video_capture = None

    async def video_stream(self):
        """Async generator yielding BGR numpy frames as they arrive.
        Mirrors state_stream()'s interface. Retries on dropped frames
        (normal over WiFi/UDP) but gives up after ~5s of nothing."""
        consecutive_failures = 0
        while not self._video_stop:
            received, frame = await asyncio.to_thread(self._video_capture.read)
            if not received:
                consecutive_failures += 1
                if consecutive_failures >= 50:
                    return
                await asyncio.sleep(0.1)
                continue
            consecutive_failures = 0
            yield frame
