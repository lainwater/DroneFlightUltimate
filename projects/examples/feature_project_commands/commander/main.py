"""
# feature_project_commands - your own keys: misc_1 / misc_2 -> your project code -> overlay

## You need
    Nothing - the simdrone runs on your PC, its video is your laptop camera
    (camera_index in config/mydrone.json).

## Run
    python run.py run -e -n feature_project_commands

## Config
    config/mydrone.json     which drone: drone_type, drone_id, ip, ...
    config/defaults.toml    controller layout
                            [video] calibration (+ ArUco settings), see core/video/calibration

## What it shows
    Keyboard 9 / 0 send misc_1 / misc_2 to project.<drone_id> (layout entry "target": "project").
    misc_1: asks the drone for its battery, the answer is drawn on the video (display.<drone_id>).
    misc_2: clears that overlay.
    Press C (connect) and J (video) first. Swap your own logic into _on_project_command().
"""

import asyncio

from core.controller import ControllerType, get_controller
from core.logger import LoggerType, get_logger
from core.video import VideoOutputType, get_videostream
from projects.base import ProjectBase


class feature_project_commands(ProjectBase):
    async def setup(self) -> None:
        # every bus message -> console, and recorded to logs/bus_logs/
        self.live_logger = get_logger(LoggerType.LIVE_CONSOLE, min_level=self.log_level)
        self.recorder.attach(self.bus)
        self.bus.subscribe("*", self.live_logger.log_bus_event)

        # drone from config/mydrone.json
        self.drone1 = self.create_drone("drone_1")

        # video window for drone1's frames; [video] in defaults.toml = calibration, ArUco settings
        self.video1 = get_videostream(
            VideoOutputType.CV2, drone_id=self.drone1.drone_id, bus=self.bus, media_dir=self.log_dir / "media", **self.app_config.get("video", {})
        )

        # controller, layout from config/defaults.toml
        layout = self.app_config.get("controller", {}).get("layout")
        self.controller = get_controller(ControllerType.KEYBOARD, drone_id=self.drone1.drone_id, bus=self.bus, layout=layout)

        # keys with "target": "project" (9 / 0) publish on project.<drone_id>
        self.presses = 0
        self.bus.subscribe(f"project.{self.drone1.drone_id}", self._on_project_command)
        self.bus.subscribe(f"data.{self.drone1.drone_id}", self._on_drone_data)

    async def main(self) -> None:
        await self.controller.start_controller()
        await self.video1.start_stream()
        print(self.controller.controls_text())
        await asyncio.Event().wait()  # runs until CTRL+C, then end_run()

    async def _on_project_command(self, topic: str, data: dict) -> None:
        """Keys with "target": "project" in the layout land here (9 = misc_1, 0 = misc_2)."""
        action = data.get("action")
        if action == "misc_1":
            # ask the drone for something - the answer arrives as data.drone1 (see _on_drone_data)
            self.presses += 1
            await self.bus.publish(f"cmd.{self.drone1.drone_id}", {"action": "get_battery"})
        elif action == "misc_2":
            # clear the overlay block (publish {} on display.<id>)
            self.presses = 0
            await self.bus.publish(f"display.{self.drone1.drone_id}", {})

    async def _on_drone_data(self, topic: str, data: dict) -> None:
        """Answers of get_* commands -> drawn top-right on the video (display.<id>)."""
        if self.presses and isinstance(data, dict) and "battery" in data:
            await self.bus.publish(f"display.{self.drone1.drone_id}", {"misc_1 presses": self.presses, "battery [%]": data["battery"]})

    async def end_run(self) -> None:
        self.bus.unsubscribe(f"project.{self.drone1.drone_id}", self._on_project_command)
        self.bus.unsubscribe(f"data.{self.drone1.drone_id}", self._on_drone_data)
        await self.shutdown_drone(self.drone1)
        if self.video1.is_running:
            await self.video1.stop_recording()
            await self.video1.stop_stream()
        await self.controller.stop_controller()
        self.recorder.detach(self.bus)
