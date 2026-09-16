'''
T8LController - Operate drone via RadioMaster T8L USB controller.
'''

import asyncio
import pygame

from core.controller.base import ControllerBase
from core.controller.implementations.rm_t8l.get_layout import (
    current_t8l_layout_as_json_path,
)


class T8LController(ControllerBase):
    def __init__(self, drone_id, bus, layout):
        super().__init__(drone_id, bus, layout)

        self.running = False
        self.controller_task = None

        self.joystick = None

        self.axes = {
            "x": 0.0,
            "y": 0.0,
            "z": 0.0,
            "yaw": 0.0,
        }

        self.switch_states = {}

    def load_config(self, layout: str) -> None:
        layout_path = current_t8l_layout_as_json_path(layout)
        self.config = self.fops.read_json(layout_path)

    async def publish_parser(self, data: dict) -> None:
        if self.bus:
            await self.bus.publish(
                f"cmd.{self.drone_id}",
                data
            )

    async def start_controller(self) -> None:
        pygame.init()
        pygame.joystick.init()

        if pygame.joystick.get_count() == 0:
            raise RuntimeError("No gamepad found.")

        self.joystick = pygame.joystick.Joystick(0)
        self.joystick.init()

        print(
            f"T8L connected: "
            f"{self.joystick.get_name()}"
        )

        self.running = True
        self.controller_task = asyncio.create_task(
            self._controller_loop()
        )

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

            # pygame.event.get() is non-blocking.
            # Give control back to asyncio.
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

        # Apply inversion.
        if config.get("invert", False):
            value = -value

        # Apply deadzone.
        deadzone = self.config.get("deadzone", 0.1)

        if abs(value) < deadzone:
            value = 0.0

        # Clamp.
        value = max(-1.0, min(1.0, value))

        # Don't publish if the value hasn't actually changed.
        if self.axes[logical_axis] == value:
            return

        self.axes[logical_axis] = value

        asyncio.create_task(
            self.publish_parser({
                "action": "rc",
                "args": {
                    "x": self.axes["x"],
                    "y": self.axes["y"],
                    "z": self.axes["z"],
                    "yaw": self.axes["yaw"],
                },
            })
        )

    def _handle_switch(self, config: dict, value: float) -> None:
        name = config["name"]

        position = self._resolve_switch_position(
            config,
            value
        )

        if position is None:
            return

        previous = self.switch_states.get(name)

        # First event only establishes the current state.
        # This prevents e.g. an already-active emergency switch
        # from firing immediately when the controller starts.
        if previous is None:
            self.switch_states[name] = position
            return

        if previous == position:
            return

        self.switch_states[name] = position

        action = config.get("positions", {}).get(
            position
        )

        if action is None:
            return

        asyncio.create_task(
            self.publish_parser({
                "action": action
            })
        )

    @staticmethod
    def _resolve_switch_position(
        config: dict,
        value: float
    ) -> str | None:

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