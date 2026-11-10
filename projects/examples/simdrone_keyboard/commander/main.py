"""
# simdrone_keyboard - fly the simdrone with the keyboard

## You need
    Nothing - the simdrone runs on your PC

## Run
    python run.py run -e -n simdrone_keyboard

## Config
    config/mydrone.json     which drone: drone_type, drone_id, ip, ...
    config/defaults.toml    controller layout
"""

import asyncio

from core.controller import ControllerType, get_controller
from core.logger import LoggerType, get_logger
from projects.base import ProjectBase


class simdrone_keyboard(ProjectBase):
    async def setup(self) -> None:
        # every bus message -> console, and recorded to logs/bus_logs/
        self.live_logger = get_logger(LoggerType.LIVE_CONSOLE, min_level=self.log_level)
        self.recorder.attach(self.bus)
        self.bus.subscribe("*", self.live_logger.log_bus_event)

        # drone from config/mydrone.json
        self.drone1 = self.create_drone("drone_1")

        # controller, layout from config/defaults.toml
        layout = self.app_config.get("controller", {}).get("layout")
        self.controller = get_controller(ControllerType.KEYBOARD, drone_id=self.drone1.drone_id, bus=self.bus, layout=layout)

    async def main(self) -> None:
        await self.controller.start_controller()
        print(self.controller.controls_text())
        await asyncio.Event().wait()  # runs until CTRL+C, then end_run()

    async def end_run(self) -> None:
        await self.shutdown_drone(self.drone1)
        await self.controller.stop_controller()
        self.recorder.detach(self.bus)
