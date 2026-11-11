"""
TelloDrone - Real DJI/Ryze Tello, controlled via UDP per the Tello
SDK 2.0 / 3.0 (3.0 = RoboMaster TT: adds expansion kit LED, dot matrix
and distance sensor - those commands answer 'error' on a plain Tello).

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
- get_position is an approxiamation
"""

import asyncio
import time
from pathlib import Path
from typing import Callable

from core.drone.base import DroneArmState, DroneBase, DroneConState, DroneFlightState, DroneType, PublishType, requires
from core.drone.implementations.DJI.tello.tellosdk import TelloSDK
from core.drone.telemetry import tello_query, tello_state

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
    # SDK 3.0 (RoboMaster TT)
    "hardware": "hardware?",  # 'TELLO' or 'RMTT' (= expansion kit attached)
    "wifi_version": "wifiversion?",  # expansion kit only
    "ap": "ap?",  # router the drone joins in station mode - expansion kit only
    "ssid": "ssid?",  # current Wi-Fi name - expansion kit only
    "ext_tof": "EXT tof?",  # distance sensor on the expansion kit, in mm (8192 = out of range)
    "ext_version": "EXT version?",  # expansion kit (ESP32) firmware
}

_FLIP_DIRECTIONS = {"left": "l", "right": "r", "forward": "f", "back": "b", "l": "l", "r": "r", "f": "f", "b": "b"}

# Expansion kit (RoboMaster TT open-source controller) - LED and 8x8 dot matrix.
# Matrix patterns are 64 characters, row by row: r = red, b = blue, p = purple, 0 = off.
_EXT_COMMANDS: dict[str, Callable[..., str]] = {
    "led": lambda r, g, b: f"EXT led {int(r)} {int(g)} {int(b)}",
    "led_pulse": lambda rate, r, g, b: f"EXT led br {rate} {int(r)} {int(g)} {int(b)}",
    "led_blink": lambda rate, r1, g1, b1, r2, g2, b2: f"EXT led bl {rate} {int(r1)} {int(g1)} {int(b1)} {int(r2)} {int(g2)} {int(b2)}",
    "matrix_pattern": lambda pattern: f"EXT mled g {pattern}",
    "matrix_clear": lambda: "EXT mled g " + "0" * 64,
    "matrix_scroll_text": lambda direction, color, rate, text: f"EXT mled {direction} {color} {rate} {text}",
    "matrix_scroll_pattern": lambda direction, rate, pattern: f"EXT mled {direction} g {rate} {pattern}",
    "matrix_show": lambda color, text: f"EXT mled s {color} {text}",  # one character, or 'heart'
    "matrix_boot_pattern": lambda pattern: f"EXT mled sg {pattern}",
    "matrix_clear_boot": lambda: "EXT mled sc",
    "matrix_brightness": lambda level: f"EXT mled sl {int(level)}",
}


# Tello models - config/mydrone.json "model". Commands a model can't do are listed with
# "models" in commands.json and answered with error NotSupported instead of being sent.
#   tello         basic Tello, SDK 1.3: hotspot only, no mission pads, no 'stop'
#   tello_edu     Tello EDU, SDK 2.0 (3.0 with firmware >= 02.05.01.17): mission pads, station mode, ...
#   tello_talent  Tello Talent = RoboMaster TT, SDK 3.0 + expansion kit (LED, dot matrix, ToF)
TELLO_MODELS = ("tello", "tello_edu", "tello_talent")
_MODEL_ALIASES = {
    "basic": "tello",
    "edu": "tello_edu",
    "talent": "tello_talent",
    "rmtt": "tello_talent",
    "tt": "tello_talent",
    "robomaster_tt": "tello_talent",
}
DEFAULT_STATE_PORT = 8890
DEFAULT_VIDEO_PORT = 11111
TAKEOFF_HOT_C = 80  # board temperature from which a refused takeoff is blamed on heat (experience, not a DJI number)
TAKEOFF_LOW_BATTERY = 10  # % below which a refused takeoff is blamed on the battery


def normalize_model(model: str | None) -> str | None:
    """'EDU' -> 'tello_edu'. None = unknown model: nothing is blocked."""
    if model in (None, "", "auto"):
        return None
    name = str(model).strip().lower().replace("-", "_").replace(" ", "_")
    name = _MODEL_ALIASES.get(name, name)
    if name not in TELLO_MODELS:
        raise ValueError(f"Unknown Tello model {model!r} - use one of {', '.join(TELLO_MODELS)}")
    return name


class TelloDrone(DroneBase):
    def __init__(self, drone_type: DroneType, drone_id: str, bus: object, **kwargs):
        super().__init__(drone_type, drone_id, bus, **kwargs)
        self.model = normalize_model(self.init_kwargs.get("model"))
        self._last_state: dict = {}  # newest telemetry (unified keys), if the state receiver runs
        self.ip = self.init_kwargs.get("ip", "192.168.10.1")
        self.cmd_port = self.init_kwargs.get("cmd_port", 8889)
        self.cmd_pc_port = self.init_kwargs.get("cmd_pc_port", 9000)
        self.state_port = int(self.init_kwargs.get("state_port", DEFAULT_STATE_PORT))
        self.video_port = int(self.init_kwargs.get("video_port", DEFAULT_VIDEO_PORT))

        self.sdk: TelloSDK | None = None
        self.data_gen_task = None
        self.video_streaming = False
        self.video_task = None
        self._camera_lock = asyncio.Lock()  # key 1/2 mashed quickly must not run two switches at once

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
        self.sdk = TelloSDK(self.ip, self.cmd_port, self.cmd_pc_port, self.state_port, self.video_port)
        await self.sdk.open_command_channel()
        ack = await self.sdk.send_and_receive("command", timeout=10)
        if ack is False:
            self.con_state = DroneConState.DISCONNECTED
            await self.sdk.close_command_channel()
        else:
            # True or None (dropped ack) both count as "probably connected" -
            # the SDK-mode command is nearly always accepted in practice.
            self.con_state = DroneConState.CONNECTED
        if ack is None:
            # Not one UDP packet came back from the drone - almost always a network/firewall problem, not the drone.
            info = (
                f"No answer from {self.ip}:{self.cmd_port}. Check: same subnet as the drone (ping {self.ip}), "
                f"PC firewall allows inbound UDP {self.cmd_pc_port}/{self.state_port}/{self.video_port} for python, "
                "no other program/drone using these ports."
            )
            await self.publish_parser(PublishType.ACK, {"cmd": "connect", "ack": "None", "info": info})
            return
        await self.publish_parser(PublishType.ACK, {"cmd": "connect", "ack": f"{ack}"})
        if ack and (self.state_port, self.video_port) != (DEFAULT_STATE_PORT, DEFAULT_VIDEO_PORT):
            # several Tellos on one PC: each sends state/video to its own ports (EDU/Talent)
            ports_ack = await self.sdk.send_and_receive(f"port {self.state_port} {self.video_port}", timeout=10)
            await self._publish_tristate_ack(f"set ports {self.state_port} {self.video_port}", ports_ack)

    @requires(DroneConState.CONNECTED)
    async def connect_via_wifi(self, ssid: str, password: str):
        """Two ways to reach a Tello: (1) the default - your PC joins
        the Tello's own hotspot, use connect() as normal; (2) this one -
        the Tello instead joins YOUR existing WiFi network (station
        mode). After this succeeds the Tello disconnects its hotspot
        and reboots onto your network with a NEW IP this app has no
        way to discover on its own (check your router's DHCP client
        list) - reconnect afterwards with connect() using that IP."""
        ack = await self.sdk.send_and_receive(f"ap {ssid} {password}", timeout=10)
        await self._publish_tristate_ack(f"connect_via_wifi {ssid}", ack)
        if ack is not False:
            await self.disconnect()

    async def disconnect(self):
        try:
            await self.stop_state_receiver()
            await self.set("disarm")
            self.flight_state = DroneFlightState.LANDED
            self.arm_state = DroneArmState.DISARMED
            self.con_state = DroneConState.DISCONNECTING
            await self.sdk.close_command_channel()
            self.con_state = DroneConState.DISCONNECTED
            await self.publish_parser(PublishType.ACK, {"cmd": "disconnect", "ack": "True"})
        except Exception as e:
            await self.publish_parser(PublishType.ERROR, {"error": str(e), "method": "disconnect"})

    # Movement
    @requires(DroneConState.CONNECTED, DroneFlightState.LANDED, DroneArmState.ARMED)
    async def takeoff(self):
        ack = await self.sdk.send_and_receive("takeoff", timeout=20)
        if ack is False:  # the Tello refused - say why, if we can tell
            info = "'takeoff' returned 'error'."
            await self.publish_parser(
                PublishType.ERROR, {"cmd": "takeoff", "error": "takeoffFailed", "info": info, "hint": await self._takeoff_refused_hint()}
            )
            return
        await self._publish_tristate_ack("takeoff", ack, on_success=lambda: setattr(self, "flight_state", DroneFlightState.INAIR))

    async def _takeoff_refused_hint(self) -> str:
        """Most common reasons the Tello refuses a takeoff: too hot, battery too low.
        Uses the last telemetry if the state receiver runs, else asks the drone."""
        temp, battery = self._last_state.get("temperature"), self._last_state.get("battery")
        if temp is None:
            raw = await self.sdk.query("temp?", timeout=3)
            temp = tello_query("temperature", raw) if isinstance(raw, str) else None
        if battery is None:
            raw = await self.sdk.query("battery?", timeout=3)
            battery = tello_query("battery", raw) if isinstance(raw, str) else None
        temp, battery = (v if isinstance(v, (int, float)) else None for v in (temp, battery))  # unreadable -> unknown
        if temp is not None and temp >= TAKEOFF_HOT_C:
            cooling = " or motor_on to cool it (EDU/Talent)" if self.model != "tello" else ""
            return f"Board is {temp:g} C - too hot to take off. Let it cool down (power off / fan){cooling}; start the video right before takeoff."
        if battery is not None and battery < TAKEOFF_LOW_BATTERY:
            return f"Battery is {battery:g} % - too low to take off. Charge it."
        status = ", ".join(f"{k} {v:g}" for k, v in (("temperature C", temp), ("battery %", battery)) if v is not None)
        return f"Check: standing level on the ground, propellers free, IMU calibration (Tello app){f' ({status})' if status else ''}."

    @requires(DroneConState.CONNECTED, DroneFlightState.INAIR)
    async def land(self):
        ack = await self.sdk.send_and_receive("land", timeout=20)
        await self._publish_tristate_ack("land", ack, on_success=lambda: setattr(self, "flight_state", DroneFlightState.LANDED))

    @requires(DroneConState.CONNECTED)
    async def emergency(self):
        ack = await self.sdk.send_and_receive("emergency", timeout=5)
        await self._publish_tristate_ack("emergency", ack, on_success=lambda: setattr(self, "flight_state", DroneFlightState.LANDED))

    # rc movement - fire-and-forget, Tello never acks this one
    @requires(DroneConState.CONNECTED, DroneFlightState.INAIR)
    async def rc(self, x: float, y: float, z: float, yaw: float):
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
    @requires(DroneConState.CONNECTED, DroneFlightState.INAIR)
    async def goto(self, x: float, y: float, z: float, speed: int = 50, mid: str | None = None):
        """Fly x/y/z cm (-500..500) at speed cm/s (10..100), relative to the
        drone - or, with mid ('m1'..'m8', 'm-1' = first pad seen, 'm-2' =
        nearest pad), to that point in the mission pad's coordinates."""
        cmd = f"go {int(x)} {int(y)} {int(z)} {int(speed)}" + (f" {mid}" if mid else "")
        ack = await self.sdk.send_and_receive(cmd, timeout=20)
        await self._publish_tristate_ack(f"goto {x} {y} {z}" + (f" {mid}" if mid else ""), ack, on_success=lambda: self.sdk.apply_goto_delta(x, y, z))

    @requires(DroneConState.CONNECTED, DroneFlightState.INAIR)
    async def curve(self, x1: float, y1: float, z1: float, x2: float, y2: float, z2: float, speed: int = 30, mid: str | None = None):
        """Fly a curve through (x1 y1 z1) to (x2 y2 z2), cm, speed 10..60 cm/s.
        The arc radius must be 0.5..10 m, otherwise the drone answers 'error'."""
        cmd = f"curve {int(x1)} {int(y1)} {int(z1)} {int(x2)} {int(y2)} {int(z2)} {int(speed)}" + (f" {mid}" if mid else "")
        ack = await self.sdk.send_and_receive(cmd, timeout=30)
        await self._publish_tristate_ack(cmd, ack, on_success=lambda: self.sdk.apply_goto_delta(x2, y2, z2))

    @requires(DroneConState.CONNECTED, DroneFlightState.INAIR)
    async def jump(self, x: float, y: float, z: float, speed: int, yaw: int, mid1: str, mid2: str):
        """Fly to (x y z) in mission pad mid1's coordinates, then find pad mid2
        and turn to `yaw` degrees relative to it."""
        cmd = f"jump {int(x)} {int(y)} {int(z)} {int(speed)} {int(yaw)} {mid1} {mid2}"
        ack = await self.sdk.send_and_receive(cmd, timeout=30)
        await self._publish_tristate_ack(cmd, ack)

    @requires(DroneConState.CONNECTED, DroneFlightState.INAIR)
    async def rotate(self, direction: str, degrees: int):
        """Turn 'cw' (clockwise) or 'ccw' by 1..360 degrees."""
        if direction not in ("cw", "ccw"):
            msg = f"rotate direction must be 'cw' or 'ccw', not '{direction}'."
            await self.publish_parser(PublishType.ERROR, {"error": "UnknownDirection", "message": msg})
            return
        ack = await self.sdk.send_and_receive(f"{direction} {int(degrees)}", timeout=15)
        turn = degrees if direction == "cw" else -degrees
        await self._publish_tristate_ack(f"rotate {direction} {degrees}", ack, on_success=lambda: self.sdk.apply_rotation(turn))

    @requires(DroneConState.CONNECTED, DroneFlightState.INAIR)
    async def flip(self, direction: str):
        """Flip 'left', 'right', 'forward' or 'back' (needs enough battery)."""
        code = _FLIP_DIRECTIONS.get(direction)
        if code is None:
            msg = f"'{direction}' is not a flip direction (left/right/forward/back)."
            await self.publish_parser(PublishType.ERROR, {"error": "UnknownDirection", "message": msg})
            return
        ack = await self.sdk.send_and_receive(f"flip {code}", timeout=15)
        await self._publish_tristate_ack(f"flip {direction}", ack)

    @requires(DroneConState.CONNECTED)
    async def stop(self):
        """Stop and hover in place RIGHT NOW - interrupts a running go/curve/move.
        Sent at once, without waiting for the running command (which holds the
        command channel until the drone answers it)."""
        self.sdk.track_rc_velocity(0, 0, 0, 0)
        self.sdk.send("stop")
        await self.publish_parser(PublishType.ACK, {"cmd": "stop", "ack": "sent"})

    # Motors / launch / reboot
    @requires(DroneConState.CONNECTED, DroneFlightState.LANDED, DroneArmState.ARMED)
    async def motor_on(self):
        """Spin the propellers slowly on the ground (cooling). Ends by itself on takeoff."""
        ack = await self.sdk.send_and_receive("motoron", timeout=10)
        await self._publish_tristate_ack("motor_on", ack)

    @requires(DroneConState.CONNECTED, DroneFlightState.LANDED)
    async def motor_off(self):
        ack = await self.sdk.send_and_receive("motoroff", timeout=10)
        await self._publish_tristate_ack("motor_off", ack)

    @requires(DroneConState.CONNECTED, DroneFlightState.LANDED, DroneArmState.ARMED)
    async def throw_fly(self):
        """Throw-to-launch: throw the drone horizontally within 5 s after this."""
        ack = await self.sdk.send_and_receive("throwfly", timeout=15)
        await self._publish_tristate_ack("throw_fly", ack, on_success=lambda: setattr(self, "flight_state", DroneFlightState.INAIR))

    @requires(DroneConState.CONNECTED)
    async def reboot(self):
        """Reboot the drone. It sends no answer on success - and the connection
        is gone afterwards, so we disconnect locally (connect again when it's back)."""
        ack = await self.sdk.send_and_receive("reboot", timeout=5)
        if ack is False:
            await self._publish_tristate_ack("reboot", ack)
            return
        await self.publish_parser(PublishType.ACK, {"cmd": "reboot", "ack": "sent", "info": "Drone reboots - connect again in ~10 s."})
        if self.video_streaming:
            await self._close_video()
            self.video_streaming = False
        await self.disconnect()

    # Expansion kit (RoboMaster TT): top LED + 8x8 dot matrix
    @requires(DroneConState.CONNECTED)
    async def ext(self, what: str, **kwargs):
        """Expansion kit LED / dot matrix - see _EXT_COMMANDS for 'what' and its args.
        A drone without the expansion kit answers 'error'."""
        builder = _EXT_COMMANDS.get(what)
        if builder is None:
            msg = f"'{what}' is not an expansion kit command. Known: {', '.join(_EXT_COMMANDS)}"
            await self.publish_parser(PublishType.ERROR, {"error": "UnknownExt", "message": msg})
            return
        cmd = builder(**kwargs)
        ack = await self.sdk.send_and_receive(cmd, timeout=5)
        await self._publish_tristate_ack(f"ext {what}", ack)

    # Step Movement
    @requires(DroneConState.CONNECTED, DroneFlightState.INAIR)
    async def steps_move(self, direction: str, distance: float):
        word = _STEP_MOVE_WORDS.get(direction)
        if word is None:
            await self.publish_parser(PublishType.ERROR, {"error": "UnknownDirection", "message": f"'{direction}' is not a valid move direction."})
            return
        ack = await self.sdk.send_and_receive(f"{word} {int(distance)}", timeout=15)
        await self._publish_tristate_ack(f"move {direction} {distance}", ack, on_success=lambda: self.sdk.apply_step_delta(direction, distance))

    # Set
    @requires(DroneConState.CONNECTED)
    async def set(self, what: str, **kwargs) -> None:

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
            # SDK 3.0 - expansion kit only
            "wifi_channel": lambda: f"wifisetchannel {int(kwargs['channel'])}",
            "multi_wifi": lambda: f"multi wifi {kwargs['ssid']} {kwargs['password']}",
        }
        if what == "camera_source":
            # Handled separately: see _switch_camera() - the video decoder
            # must be reset when the camera (and so the resolution) changes.
            async with self._camera_lock:
                ack = await self._switch_camera(bool(kwargs.get("downward")))
            await self._publish_tristate_ack(f"set {what} {kwargs}", ack)
            return

        builder = command_builders.get(what)
        if builder is None:
            await self.publish_parser(PublishType.ERROR, {"error": "UnknownSet", "message": f"'{what}' is not settable on Tello."})
            return

        ack = await self.sdk.send_and_receive(builder(), timeout=10)
        await self._publish_tristate_ack(f"set {what} {kwargs}", ack)

    # GET
    @requires(DroneConState.CONNECTED)
    async def get(self, what: str):
        if what == "position":
            # Dead-reckoned estimate, not a real sensor reading - see
            # TelloSDK's position tracking. Labeled clearly so it's
            # never mistaken for ground truth.
            await self.publish_parser(PublishType.DATA, {"position": self.sdk.get_position(), "estimated": True})  # cm, x right, y forward
            return

        query = _QUERY_COMMANDS.get(what)
        if query is None:
            await self.publish_parser(PublishType.ERROR, {"error": "UnknownGet", "message": f"'{what}' is not readable on Tello."})
            return

        raw = await self.sdk.query(query, timeout=7)
        if raw is None:
            await self.publish_parser(PublishType.ERROR, {"error": "QueryTimeout", "message": f"No response querying '{what}'."})
            return

        await self.publish_parser(PublishType.DATA, {what: tello_query(what, raw)})  # unified units, see core/drone/telemetry.py

    @requires(DroneConState.CONNECTED)
    async def start_video(self):
        # Socket first, so no packet (and no keyframe) is missed after streamon.
        await self._open_video()
        ack = await self.sdk.send_and_receive("streamon", timeout=10)
        if ack is False:
            await self._close_video()
        await self._publish_tristate_ack("start_video", ack, on_success=lambda: setattr(self, "video_streaming", True))

    @requires(DroneConState.CONNECTED)
    async def stop_video(self):
        # Order no longer matters: the receiver never blocks longer than 0.5 s.
        await self._close_video()
        ack = await self.sdk.send_and_receive("streamoff", timeout=10)
        await self._publish_tristate_ack("stop_video", ack, on_success=lambda: setattr(self, "video_streaming", False))

    async def _open_video(self) -> None:
        await self.sdk.open_video_channel()
        if self.video_task is None or self.video_task.done():
            self.video_task = asyncio.create_task(self._consume_video_stream())

    async def _close_video(self) -> None:
        self.sdk.stop_video_stream()
        if self.video_task:
            await self.video_task
            self.video_task = None
        await self.sdk.close_video_channel()

    async def _switch_camera(self, downward: bool) -> bool | None:
        """'downvision' switches the camera on the fly - the stream keeps
        running, only its resolution changes (960x720 <-> 320x240). So: NO
        streamoff/streamon and no reopening (that gap is what used to freeze
        the video). We only reset the decoder so it starts clean on the new
        camera's next keyframe."""
        ack = await self.sdk.send_and_receive(f"downvision {1 if downward else 0}", timeout=10)
        if ack is not False:
            self.sdk.reset_video_decoder()
        return ack

    async def _consume_video_stream(self):
        """Analog to _consume_state_stream"""
        seq = 0
        async for frame in self.sdk.video_stream():
            seq += 1
            await self.publish_parser(PublishType.FRAME, {"ts": time.time(), "seq": seq, "encoding": "bgr24", "frame": frame})

    # Other
    @requires(DroneConState.CONNECTED)
    async def start_state_receiver(self):
        """Starts a background task that publishes every item the SDK's
        state_stream yields, until stop_state_receiver() cancels it."""
        await self.sdk.open_state_channel()
        self.data_gen_task = asyncio.create_task(self._consume_state_stream())

    async def stop_state_receiver(self):
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
        async for raw in self.sdk.state_stream():
            if "h" in raw:
                self.sdk.position["z"] = raw["h"]
            if isinstance(raw.get("yaw"), (int, float)):
                self.sdk.heading = raw["yaw"]  # Tello yaw: relative to takeoff, clockwise positive
            self._last_state = tello_state(raw, self.sdk.get_position())
            await self.publish_parser(PublishType.STATE, self._last_state)
