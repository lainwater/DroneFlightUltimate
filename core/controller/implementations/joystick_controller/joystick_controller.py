'''
JoystickController - Operate a drone via any pygame-recognized
joystick/gamepad (RadioMaster T8L, an Xbox controller, ...).

One class for every device - what differs between a T8L and, say, an
Xbox controller is only WHICH axis/button maps to WHICH logical rc
axis or action, and that lives entirely in the JSON profile (t8l.json,
xbox.json, ...), selected via `layout` (see get_layout.py for why
there's no auto-detection, unlike the keyboard controller).
'''

import asyncio
import pygame

from core.controller.base import ControllerBase
from core.controller.implementations.joystick_controller.get_layout import (
    current_joystick_layout_as_json_path,
)


class JoystickController(ControllerBase):
    def __init__(self, drone_id, bus, layout):
        super().__init__(drone_id, bus, layout)
        self.running = False
        self.controller_task = None
        self.joystick = None
        self.axes = {"x": 0.0, "y": 0.0, "z": 0.0, "yaw": 0.0}
        self.switch_states: dict[str, str] = {}

    def load_config(self, layout: str) -> None:
        layout_path = current_joystick_layout_as_json_path(layout)
        self.config = self.fops.read_json(layout_path)

    async def publish_parser(self, data: dict) -> None:
        if self.bus:
            await self.bus.publish(f"cmd.{self.drone_id}", data)

    async def start_controller(self) -> None:
        pygame.init()
        pygame.joystick.init()
        if pygame.joystick.get_count() == 0:
            raise RuntimeError("No joystick/gamepad found.")

        self.joystick = pygame.joystick.Joystick(0)
        self.joystick.init()
        print(f"Joystick connected: {self.joystick.get_name()}")

        self.running = True
        self.controller_task = asyncio.create_task(self._controller_loop())

    async def stop_controller(self) -> None:
        self.running = False
        if self.controller_task:
            await self.controller_task
            self.controller_task = None
        if self.joystick:
            self.joystick.quit()
            self.joystick = None
        pygame.joystick.quit()
        pygame.quit()

    async def _controller_loop(self) -> None:
        while self.running:
            self._process_events()
            # pygame.event.get() is non-blocking - give control back
            # to asyncio between polls.
            await asyncio.sleep(0.005)

    def _process_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.JOYAXISMOTION:
                self._handle_axis(event.axis, event.value)

    def _handle_axis(self, axis: int, value: float) -> None:
        axis_config = self.config.get("axes", {}).get(str(axis))
        if not axis_config:
            return

        input_type = axis_config.get("type")
        if input_type == "rc":
            self._handle_rc_axis(axis_config, value)
        elif input_type == "switch":
            self._handle_switch(axis_config, value)

    def _handle_rc_axis(self, config: dict, value: float) -> None:
        logical_axis = config["axis"]

        if config.get("invert", False):
            value = -value

        deadzone = self.config.get("deadzone", 0.1)
        if abs(value) < deadzone:
            value = 0.0
        value = max(-1.0, min(1.0, value))

        # Don't publish if the value hasn't actually changed - pygame
        # fires axis events continuously, not just on real movement.
        if self.axes[logical_axis] == value:
            return
        self.axes[logical_axis] = value

        # Always send the FULL current vector, not just this one axis -
        # this is what lets two axes moved at once (e.g. x and z)
        # combine into one command, same principle as the keyboard
        # controller's held-key combination.
        self._publish({"action": "rc", "args": dict(self.axes)})

    def _handle_switch(self, config: dict, value: float) -> None:
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
        self._publish({"action": action})

    def _publish(self, data: dict) -> None:
        """Schedule the publish on the running event loop and make
        sure any exception actually surfaces - an untracked task's
        failure would otherwise just look like 'the switch did
        nothing', the same trap the keyboard controller had with
        run_coroutine_threadsafe (here it's create_task instead, since
        _process_events already runs on the event loop's own thread -
        no cross-thread handoff needed)."""
        task = asyncio.create_task(self.publish_parser(data))
        task.add_done_callback(self._log_task_exception)

    @staticmethod
    def _log_task_exception(task: asyncio.Task) -> None:
        exc = task.exception()
        if exc is not None:
            import traceback
            traceback.print_exception(type(exc), exc, exc.__traceback__)

    @staticmethod
    def _resolve_switch_position(config: dict, value: float) -> str | None:
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