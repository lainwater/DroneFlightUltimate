"""
# sim_yolo - simdrone that starts everything by itself: telemetry, video, stats overlay, YOLO

## You need
    Nothing but a laptop camera (the simdrone's video) and ultralytics (pip install -U ultralytics).

## Run
    python run.py run -m -n sim_yolo

## What it does
    connect -> arm -> telemetry -> laptop camera -> window with stats overlay -> YOLO boxes.
    Fly with the keyboard (T takeoff, WASD + arrows, L land). The stats overlay shows the
    unified telemetry keys (battery, height).
"""

import asyncio

from core.controller import ControllerType, get_controller
from core.logger import LoggerType, get_logger
from core.video import VideoOutputType, get_videostream
from projects.base import ProjectBase


class sim_yolo(ProjectBase):
    async def setup(self) -> None:
        self.live_logger = get_logger(LoggerType.LIVE_CONSOLE, min_level=self.log_level, exclude_topics=("frame.*", "state.*"))
        self.recorder.attach(self.bus)
        self.bus.subscribe("*", self.live_logger.log_bus_event)

        self.drone1 = self.create_drone("drone_1")
        self.video1 = get_videostream(
            VideoOutputType.CV2, drone_id=self.drone1.drone_id, bus=self.bus, media_dir=self.log_dir / "media", **self.app_config.get("video", {})
        )
        layout = self.app_config.get("controller", {}).get("layout")
        self.controller = get_controller(ControllerType.KEYBOARD, drone_id=self.drone1.drone_id, bus=self.bus, layout=layout)

    async def main(self) -> None:
        await self.controller.start_controller()
        print(self.controller.controls_text())
        for action in ("connect", "set_arm", "start_state_receiver", "start_video"):  # = keys C, V, I, J
            await self.bus.publish(f"cmd.{self.drone1.drone_id}", {"action": action})
        await self.video1.start_stream()
        await self.video1.turn_on_display_state_data(("ts", "fps", "battery", "height", "attitude"))
        await self.video1.start_detection()
        await asyncio.Event().wait()

    async def end_run(self) -> None:
        await self.shutdown_drone(self.drone1)
        if self.video1.is_running:
            await self.video1.stop_recording()
            await self.video1.stop_stream()
        await self.controller.stop_controller()
        self.recorder.detach(self.bus)
