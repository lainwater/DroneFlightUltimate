"""
# vicon_yolo - keyboard flight with video, YOLO and the Vicon pose on the video

## You need
    Tello EDU / Talent on the Vicon lab network (station mode, ip in config/mydrone.json),
    vicon_dssdk (from the Vicon SDK folder), ultralytics.

## Run
    python run.py run -m -n vicon_yolo

## What it does
    Like examples/feature_vicon plus YOLO boxes. vicon.<id> (20 Hz, newest data only) is turned
    into text top-right. Keys: the usual keyboard_video layout (C connect, J video, 3/4 YOLO, ...).
"""

import asyncio

from core.controller import ControllerType, get_controller
from core.logger import LoggerType, get_logger
from core.vicon import get_vicon
from core.video import VideoOutputType, get_videostream
from projects.base import ProjectBase


def vicon_text(data: dict) -> dict:
    """vicon.<id> message -> overlay block."""
    if data.get("occluded"):
        return {"VICON": f"{data.get('subject')}  OCCLUDED / not visible"}
    return {
        "VICON": data.get("subject"),
        "x y z [mm]": f"{data['x']:8.1f} {data['y']:8.1f} {data['z']:8.1f}",
        "r p y [deg]": f"{data['roll']:6.1f} {data['pitch']:6.1f} {data['yaw']:6.1f}",
        "frame": data.get("frame"),
    }


class vicon_yolo(ProjectBase):
    async def setup(self) -> None:
        # vicon.*, display.* (20x/s) and YOLO results (every inference) stay out of the console
        self.live_logger = get_logger(
            LoggerType.LIVE_CONSOLE, min_level=self.log_level, exclude_topics=("frame.*", "vicon.*", "display.*", "data.stream.*")
        )
        self.recorder.exclude_topics = ("frame.*", "display.*")  # display.* = text copy of vicon.*
        self.recorder.attach(self.bus)
        self.bus.subscribe("*", self.live_logger.log_bus_event)

        self.drone1 = self.create_drone("drone_1")
        self.drone_id = self.drone1.drone_id
        self.video1 = get_videostream(
            VideoOutputType.CV2, drone_id=self.drone_id, bus=self.bus, media_dir=self.log_dir / "media", **self.app_config.get("video", {})
        )
        vicon_conf = self.app_config.get("vicon", {})
        self.vicon = get_vicon(drone_id=self.drone_id, bus=self.bus, **vicon_conf)
        self.bus.subscribe(f"vicon.{self.drone_id}", self.on_vicon)
        layout = self.app_config.get("controller", {}).get("layout")
        self.controller = get_controller(ControllerType.KEYBOARD, drone_id=self.drone_id, bus=self.bus, layout=layout)

    async def on_vicon(self, topic: str, data: dict) -> None:
        await self.bus.publish(f"display.{self.drone_id}", vicon_text(data))

    async def main(self) -> None:
        await self.controller.start_controller()
        await self.video1.start_stream()
        await self.vicon.start()
        await self.video1.start_detection()
        print(self.controller.controls_text())
        await asyncio.Event().wait()

    async def end_run(self) -> None:
        await self.vicon.stop()
        self.bus.unsubscribe(f"vicon.{self.drone_id}", self.on_vicon)
        await self.shutdown_drone(self.drone1)
        if self.video1.is_running:
            await self.video1.stop_recording()
            await self.video1.stop_stream()
        await self.controller.stop_controller()
        self.recorder.detach(self.bus)
