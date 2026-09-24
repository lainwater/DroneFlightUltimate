"""
JoystickController - Operate a drone via any pygame-recognized
joystick/gamepad.

One class for every device - what differs between a T8L and, say, an
Xbox controller is only WHICH axis/button maps to WHICH logical rc
axis or action, and that lives entirely in the JSON profile (t8l.json,
xbox.json, ...), selected via `layout`.

If you want to map different controller inputs to different bus events,
edit or create a new .json and put it in the layout arg on get_controller(...).
"""

import asyncio
from os import environ
from pathlib import Path

environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame

from core.controller.base import ControllerBase

POLLING_RATE = 200


class JoystickController(ControllerBase):
    def __init__(self, drone_id, bus, layout):
        super().__init__(drone_id, bus, layout)
        self.is_running = False
        self.controller_task = None
        self.joystick = None
        self.axes = {"x": 0.0, "y": 0.0, "z": 0.0, "yaw": 0.0}
        self.switch_states: dict[str, str] = {}

    async def start_controller(self) -> None:
        pygame.init()
        pygame.joystick.init()
        if pygame.joystick.get_count() == 0:
            raise RuntimeError("No joystick/gamepad found.")

        self.joystick = pygame.joystick.Joystick(0)
        self.joystick.init()
        await self._publish_parser("status", f"Joystick connected: {self.joystick.get_name()}")

        self.is_running = True
        self.controller_task = asyncio.create_task(self._controller_loop())

    async def stop_controller(self) -> None:
        self.is_running = False
        if self.controller_task:
            await self.controller_task
            self.controller_task = None
        if self.joystick:
            self.joystick.quit()
            self.joystick = None
        pygame.joystick.quit()
        pygame.quit()

    def _load_layout(self, layout: str = "t8l") -> None:
        if layout is None:
            layout = "t8l"
        layout_path = Path(__file__).parent / f"{layout}.json"
        self.config = self.fops.read_json(layout_path)

    async def _publish_parser(self, _type: str, data: dict) -> None:
        if self.bus:
            if _type == "cmd":
                await self.bus.publish(f"cmd.{self.drone_id}", data)
            elif _type == "status":
                await self.bus.publish(f"state.joystick-{self.layout}.{self.drone_id}", data)
            elif _type == "error":
                await self.bus.publish(f"error.joystick-{self.layout}.{self.drone_id}", data)

    async def _controller_loop(self) -> None:
        """Actual loop of controller with 1/POLLING_RATE (see top) time inbetween processing events."""
        while self.is_running:
            if self.is_turned_on:
                try:
                    self._process_events()
                    await asyncio.sleep(1 / POLLING_RATE)
                except Exception as e:
                    await self._publish_parser("error", {"exception": e})

    def _process_events(self) -> None:
        """Process pygame events. What method to call by event type."""
        for event in pygame.event.get():
            if event.type == pygame.JOYAXISMOTION:
                self._handle_axis(event.axis, event.value)

    def _handle_axis(self, axis: int, value: float) -> None:
        """Handle axes from event with specified config. Seperates type from config 'rc' and 'switch'
        (sometimes controller input tri state switches are label axes by pygame)."""
        axis_config = self.config.get("axes", {}).get(str(axis))
        if not axis_config:
            return

        input_type = axis_config.get("type")
        if input_type == "rc":
            self._handle_rc_axis(axis_config, value)
        elif input_type == "switch":
            self._handle_switch(axis_config, value)

    def _handle_rc_axis(self, config: dict, value: float) -> None:
        """Handle layout type 'rc' axes (usually used for actual joysticks)"""
        logical_axis = config["axis"]
        if config.get("invert", False):
            value = -value

        deadzone = self.config.get("deadzone", 0.15)
        if abs(value) < deadzone:
            value = 0.0
        value = max(-1.0, min(1.0, value))

        # Don't publish if the value hasn't actually changed - pygame
        # fires axis events continuously, not just on real movement.
        if self.axes[logical_axis] == value:
            return
        self.axes[logical_axis] = value

        # Always send the FULL current vector, not just this one axis -
        # this is what lets two axes moved at once
        self._publish("cmd", {"action": "rc", "args": dict(self.axes)})

    def _handle_switch(self, config: dict, value: float) -> None:
        """Handle layout type 'switch' axes (for example on t8l this is the tri state switches)"""
        name = config["name"]
        position = self._resolve_switch_position(config, value)
        if position is None:
            return

        previous = self.switch_states.get(name)
        # First event only establishes the current state - prevents an
        # already-flipped switch from firing the instant the
        # controller starts, before the user has touched anything.
        if previous is None:
            self.switch_states[name] = position
            return
        if previous == position:
            return
        self.switch_states[name] = position

        action = config.get("positions", {}).get(position)
        if action is None:
            return
        self._publish("cmd", {"action": action})

    @staticmethod
    def _resolve_switch_position(config: dict, value: float) -> str | None:
        """Resloves layout 'switch' types up, middle, down positions. Works for two state and tri state switches"""
        positions = config.get("positions", {})

        # Three-position switch.
        if "middle" in positions:
            if value < -0.5:
                return "up"
            if value > 0.5:
                return "down"
            return "middle"

        # Two-position switch.
        if value < 0:
            return "negative"
        return "positive"

    def _publish(self, _type: str = "cmd", data: dict = {}) -> None:
        """Schedule the publish on the running event loop and make
        sure any exception actually surfaces - an untracked task's
        failure would otherwise just look like 'the switch did nothing'"""
        task = asyncio.create_task(self._publish_parser(_type, data))
        task.add_done_callback(self._log_task_exception)

    @staticmethod
    def _log_task_exception(task: asyncio.Task) -> None:
        """Create traceback in case something went wrong after publishing."""
        exc = task.exception()
        if exc is not None:
            import traceback

            traceback.print_exception(type(exc), exc, exc.__traceback__)
