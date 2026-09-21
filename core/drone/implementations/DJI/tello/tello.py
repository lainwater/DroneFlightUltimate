"""
TelloDrone - Real DJI/Ryze Tello, controlled via UDP per the Tello
SDK 2.0.

- arm()/disarm() send NO command to the drone - the real Tello has no
  arming concept at all, it goes straight from "connected" to
  "takeoff". This is kept as a pure software-level safety gate so the
  shared takeoff() guard (same interface as SimDrone) still works the
  same way regardless of which drone type is connected.
- rc() is fire-and-forget (TelloSDK.send(), not send_and_receive()) -
  the real Tello never acknowledges the 'rc' command.
- Every other command uses a THREE-way ack: True ('ok'), False
  ('error'), or None (no response within timeout - the command may
  have still worked, UDP just dropped the reply). See
  _publish_tristate_ack().
- get_position isn't available - a real Tello has no absolute position
  sensor without mission pads. It isn't in commands.json, so execute()
  reports it cleanly as unsupported instead of crashing.
"""

import asyncio
from pathlib import Path
from typing import Callable

from core.drone.base import DroneArmState, DroneBase, DroneConState, DroneFlightState, DroneType, PublishType
from core.drone.implementations.DJI.tello.tellosdk import TelloSDK, _coerce_number, _parse_state_string

_STEP_MOVE_WORDS = {
    "forward": "forward",
    "backward": "back",
    "left": "left",
    "right": "right",
    "up": "up",
    "down": "down",
}

_QUERY_COMMANDS = {
    "battery": "battery?",
    "speed": "speed?",
    "flight_time": "time?",
    "wifi_snr": "wifi?",
    "sdk_version": "sdk?",
    "serial_number": "sn?",
    "height": "height?",
    "temperature": "temp?",
    "attitude": "attitude?",
    "barometer": "baro?",
    "acceleration": "acceleration?",
    "tof": "tof?",
}


class TelloDrone(DroneBase):
    def __init__(self, drone_type: DroneType, drone_id: str, bus: object, **kwargs):
        super().__init__(drone_type, drone_id, bus, **kwargs)
        self.ip = self.init_kwargs.get("ip", "192.168.10.1")
        self.cmd_port = self.init_kwargs.get("cmd_port", 8889)
        self.cmd_pc_port = self.init_kwargs.get("cmd_pc_port", 9000)
        self.state_port = self.init_kwargs.get("state_port", 8890)
        self.video_port = self.init_kwargs.get("video_port", 11111)

        # Built fresh in connect(), not here - a real UDP endpoint has
        # to actually bind at connect-time, and a reconnect after
        # disconnect() should get a new transport, not reuse a closed one.
        self.sdk: TelloSDK | None = None
        self.data_gen_task = None
        self.video_streaming = False

    @property
    def config_dir(self) -> Path:
        return Path(__file__).parent

    async def _publish_tristate_ack(self, cmd_label: str, ack: bool | None, on_success: Callable[[], None] | None = None) -> None:
        """ack is True ('ok'), False ('error'), or None (no response -
        command may have still worked, we just don't know)."""
        if ack is True:
            await self.publish_parser(PublishType.ACK, {"cmd": cmd_label, "ack": "True"})
            if on_success:
                on_success()
        elif ack is None:
            await self.publish_parser(
                PublishType.ACK,
                {
                    "cmd": cmd_label,
                    "ack": "unknown",
                    "info": "No response within timeout - command may have still succeeded.",
                },
            )
            # Optimistic: the real Tello frequently drops the ack over
            # UDP while still executing the command, so we update
            # local state as if it worked rather than getting stuck.
            if on_success:
                on_success()
        else:
            await self.publish_parser(
                PublishType.ERROR,
                {
                    "cmd": cmd_label,
                    "error": f"{cmd_label}Failed",
                    "info": f"'{cmd_label}' returned 'error'.",
                },
            )

    # General
    async def connect(self):
        self.con_state = DroneConState.CONNECTING
        self.sdk = TelloSDK(self.ip, self.cmd_port, self.cmd_pc_port, self.state_port)
        await self.sdk.open_command_channel()
        ack = await self.sdk.send_and_receive("command", timeout=10)
        if ack is False:
            self.con_state = DroneConState.DISCONNECTED
            await self.sdk.close_command_channel()
        else:
            # True or None (dropped ack) both count as "probably connected" -
            # the SDK-mode command is nearly always accepted in practice.
            self.con_state = DroneConState.CONNECTED
        await self.publish_parser(PublishType.ACK, {"cmd": "connect", "ack": f"{ack}"})

    async def connect_via_wifi(self, ssid: str, password: str):
        """Two ways to reach a Tello: (1) the default - your PC joins
        the Tello's own hotspot, use connect() as normal; (2) this one -
        the Tello instead joins YOUR existing WiFi network (station
        mode). After this succeeds the Tello disconnects its hotspot
        and reboots onto your network with a NEW IP this app has no
        way to discover on its own (check your router's DHCP client
        list) - reconnect afterwards with connect() using that IP."""
        if not await self._require_state(DroneConState.CONNECTED, "connect_via_wifi"):
            return
        ack = await self.sdk.send_and_receive(f"ap {ssid} {password}", timeout=10)
        await self._publish_tristate_ack(f"connect_via_wifi {ssid}", ack)
        if ack is not False:
            await self.disconnect()

    async def disconnect(self):
        if not await self._require_state(DroneConState.CONNECTED, "disconnect"):
            return
        await self.stop_state_reciever()
        await self.set("disarm")
        self.con_state = DroneConState.DISCONNECTING
        await self.sdk.close_command_channel()
        self.con_state = DroneConState.DISCONNECTED
        await self.publish_parser(PublishType.ACK, {"cmd": "disconnect", "ack": "True"})

    # Movement
    async def takeoff(self):
        if not await self._require_state(DroneConState.CONNECTED, "takeoff"):
            return
        if not await self._require_state(DroneFlightState.LANDED, "takeoff"):
            return
        if not await self._require_state(DroneArmState.ARMED, "takeoff"):
            return
        ack = await self.sdk.send_and_receive("takeoff", timeout=20)
        await self._publish_tristate_ack("takeoff", ack, on_success=lambda: setattr(self, "flight_state", DroneFlightState.INAIR))

    async def land(self):
        if not await self._require_state(DroneConState.CONNECTED, "land"):
            return
        if not await self._require_state(DroneFlightState.INAIR, "land"):
            return
        ack = await self.sdk.send_and_receive("land", timeout=20)
        await self._publish_tristate_ack("land", ack, on_success=lambda: setattr(self, "flight_state", DroneFlightState.LANDED))

    async def emergency(self):
        if not await self._require_state(DroneConState.CONNECTED, "emergency"):
            return
        ack = await self.sdk.send_and_receive("emergency", timeout=5)
        await self._publish_tristate_ack("emergency", ack, on_success=lambda: setattr(self, "flight_state", DroneFlightState.LANDED))

    # rc movement - fire-and-forget, Tello never acks this one
    async def rc(self, x: float, y: float, z: float, yaw: float):
        if not await self._require_state(DroneConState.CONNECTED, "rc"):
            return
        if not await self._require_state(DroneFlightState.INAIR, "rc"):
            return
        a, b, c, d = (self._to_tello_rc(v) for v in (x, y, z, yaw))
        self.sdk.send(f"rc {a} {b} {c} {d}")
        self.sdk.track_rc_velocity(x, y, z, yaw)
        await self.publish_parser(PublishType.ACK, {"cmd": f"rc {x} {y} {z} {yaw}", "ack": "sent"})

    @staticmethod
    def _to_tello_rc(value: float) -> int:
        """Our internal rc axes are -1..1 (keyboard) or -1.0..1.0
        (joystick); the real Tello's rc command wants integers -100..100."""
        return max(-100, min(100, round(value * 100)))

    # goto pos movement
    async def goto(self, x: float, y: float, z: float, speed: int = 50):
        if not await self._require_state(DroneConState.CONNECTED, "goto"):
            return
        if not await self._require_state(DroneFlightState.INAIR, "goto"):
            return
        ack = await self.sdk.send_and_receive(f"go {int(x)} {int(y)} {int(z)} {int(speed)}", timeout=20)
        await self._publish_tristate_ack(f"goto {x} {y} {z}", ack, on_success=lambda: self.sdk.apply_goto_delta(x, y, z))

    # Step Movement
    async def steps_move(self, direction: str, distance: float):
        if not await self._require_state(DroneConState.CONNECTED, f"move {direction}"):
            return
        if not await self._require_state(DroneFlightState.INAIR, f"move {direction}"):
            return
        word = _STEP_MOVE_WORDS.get(direction)
        if word is None:
            await self.publish_parser(PublishType.ERROR, {"error": "UnknownDirection", "message": f"'{direction}' is not a valid move direction."})
            return
        ack = await self.sdk.send_and_receive(f"{word} {int(distance)}", timeout=15)
        await self._publish_tristate_ack(f"move {direction} {distance}", ack, on_success=lambda: self.sdk.apply_step_delta(direction, distance))

    # Set
    async def set(self, what: str, **kwargs) -> None:
        if not await self._require_state(DroneConState.CONNECTED, f"set {what}"):
            return

        if what == "arm":
            # No real command - see the class docstring.
            self.arm_state = DroneArmState.ARMED
            await self.publish_parser(PublishType.ACK, {"cmd": "set arm", "ack": "True"})
            return
        if what == "disarm":
            self.arm_state = DroneArmState.DISARMED
            await self.publish_parser(PublishType.ACK, {"cmd": "set disarm", "ack": "True"})
            return

        command_builders: dict[str, Callable[[], str]] = {
            "speed": lambda: f"speed {int(kwargs['speed'])}",
            "own_wifi": lambda: f"wifi {kwargs['ssid']} {kwargs['password']}",
            "ports": lambda: f"port {int(kwargs['state_port'])} {int(kwargs['video_port'])}",
            "mission_pad_detection": lambda: "mon" if kwargs.get("enabled") else "moff",
            "mission_pad_direction": lambda: f"mdirection {int(kwargs['direction'])}",
            "camera_source": lambda: f"downvision {1 if kwargs.get('downward') else 0}",
            "video_fps": lambda: f"setfps {kwargs['fps']}",
            "video_bitrate": lambda: f"setbitrate {int(kwargs['bitrate'])}",
        }
        builder = command_builders.get(what)
        if builder is None:
            await self.publish_parser(PublishType.ERROR, {"error": "UnknownSet", "message": f"'{what}' is not settable on Tello."})
            return

        ack = await self.sdk.send_and_receive(builder(), timeout=10)
        await self._publish_tristate_ack(f"set {what} {kwargs}", ack)

    # GET
    async def get(self, what: str):
        if not await self._require_state(DroneConState.CONNECTED, f"get {what}"):
            return
        if what == "position":
            # Dead-reckoned estimate, not a real sensor reading - see
            # TelloSDK's position tracking. Labeled clearly so it's
            # never mistaken for ground truth.
            await self.publish_parser(PublishType.DATA, {"position": self.sdk.get_position(), "estimated": True})
            return

        query = _QUERY_COMMANDS.get(what)
        if query is None:
            await self.publish_parser(PublishType.ERROR, {"error": "UnknownGet", "message": f"'{what}' is not readable on Tello."})
            return

        raw = await self.sdk.query(query, timeout=7)
        if raw is None:
            await self.publish_parser(PublishType.ERROR, {"error": "QueryTimeout", "message": f"No response querying '{what}'."})
            return

        value = _parse_state_string(raw) if what == "attitude" else _coerce_number(raw)
        await self.publish_parser(PublishType.DATA, {what: value})

    async def start_video(self):
        if not await self._require_state(DroneConState.CONNECTED, "start_video"):
            return
        ack = await self.sdk.send_and_receive("streamon", timeout=10)
        await self._publish_tristate_ack("start_video", ack, on_success=lambda: setattr(self, "video_streaming", True))

    async def stop_video(self):
        if not await self._require_state(DroneConState.CONNECTED, "stop_video"):
            return
        ack = await self.sdk.send_and_receive("streamoff", timeout=10)
        await self._publish_tristate_ack("stop_video", ack, on_success=lambda: setattr(self, "video_streaming", False))

    async def get_frame(self):
        raise NotImplementedError(
            "Video pipeline not implemented yet - see core/video. "
            "streamon/streamoff already work; decoding the H264 stream "
            f"on port {self.video_port} comes later."
        )

    # Other
    async def start_state_reciever(self):
        """Starts a background task that publishes every item the SDK's
        state_stream yields, until stop_state_reciever() cancels it."""
        if not await self._require_state(DroneConState.CONNECTED, "start_state_reciever"):
            return
        await self.sdk.open_state_channel()
        self.data_gen_task = asyncio.create_task(self._consume_state_stream())

    async def stop_state_reciever(self):
        """Cancel the background task and wait for it to actually stop,
        so we don't leave an unhandled CancelledError floating around."""
        if self.data_gen_task:
            self.data_gen_task.cancel()
            try:
                await self.data_gen_task
            except asyncio.CancelledError:
                pass
            self.data_gen_task = None
        if self.sdk:
            await self.sdk.close_state_channel()

    async def _consume_state_stream(self):
        """The actual loop: as soon as the SDK yields a data point,
        sync z with the real 'h' field (Tello has a real height sensor,
        unlike x/y which stay pure dead-reckoning) and publish it."""
        async for i in self.sdk.state_stream():
            if "h" in i:
                self.sdk.position["z"] = i["h"]
            await self.publish_parser(PublishType.STATE, i)
