"""
# tello_keyboard_video - fly a real DJI Tello with the keyboard, video window on

## You need
    A DJI Tello. Default ip 192.168.10.1 = PC on the Tello's own hotspot.
    Tello on your network (station mode)? Put its ip in config/mydrone.json
    (set it up with: python -m tools.set_tello_wifi --help).

## Run
    python run.py run -e -n tello_keyboard_video

## Config
    config/mydrone.json     which drone: drone_type, drone_id, ip, ...
    config/defaults.toml    controller layout
                            [video] calibration (+ ArUco settings), see core/video/calibration

## Video
    The window opens at start; the video itself starts with the drone video key/switch.
"""

import asyncio

from core.controller import ControllerType, get_controller
from core.logger import LoggerType, get_logger
from core.video import VideoOutputType, get_videostream
from projects.base import ProjectBase


class tello_keyboard_video(ProjectBase):
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

    async def main(self) -> None:
        await self.controller.start_controller()
        await self.video1.start_stream()
        print(self.controller.controls_text())
        await asyncio.Event().wait()  # runs until CTRL+C, then end_run()

    async def end_run(self) -> None:
        await self.shutdown_drone(self.drone1)
        if self.video1.is_running:
            await self.video1.stop_recording()
            await self.video1.stop_stream()
        await self.controller.stop_controller()
        self.recorder.detach(self.bus)
