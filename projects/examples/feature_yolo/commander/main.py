"""
# feature_yolo - YOLO object detection on the drone video

## You need
    A DJI Tello. Default ip 192.168.10.1 = PC on the Tello's own hotspot.
    Tello on your network (station mode)? Put its ip in config/mydrone.json
    (set it up with: python -m tools.set_tello_wifi --help).
    ultralytics installed (pip install -U ultralytics); model: core/video/implementations/cv2/yolo26n.pt

## Run
    python run.py run -e -n feature_yolo

## Config
    config/mydrone.json     which drone: drone_type, drone_id, ip, ...
    config/defaults.toml    controller layout
                            [video] calibration (+ ArUco settings), see core/video/calibration

## What it shows
    YOLO runs on every frame it can keep up with (one at a time, in a thread - the video
    never stalls). Boxes on the video, object count per label top-right.
    Keys: 3/4 YOLO on/off. Try it without a Tello: drone_type "sim_simdrone" (+ "port": "6767").
"""

import asyncio

from core.controller import ControllerType, get_controller
from core.logger import LoggerType, get_logger
from core.video import VideoOutputType, get_videostream
from projects.base import ProjectBase


class feature_yolo(ProjectBase):
    async def setup(self) -> None:
        # every bus message -> console (minus the 20-30/s ones), and recorded to logs/bus_logs/
        self.live_logger = get_logger(LoggerType.LIVE_CONSOLE, min_level=self.log_level, exclude_topics=("frame.*", "data.stream.*", "display.*"))
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

        self.bus.subscribe(f"data.stream.{self.drone1.drone_id}", self._on_detections)

    async def main(self) -> None:
        await self.controller.start_controller()
        await self.video1.start_stream()
        await self.video1.start_detection(conf=0.4, publish=True)  # publish -> data.stream.<id>
        print(self.controller.controls_text())
        await asyncio.Event().wait()  # runs until CTRL+C, then end_run()

    async def _on_detections(self, topic: str, data: dict) -> None:
        """data.stream.<id> carries {"detections": [{"label", "class_id", "conf", "box"}, ...]}.
        Here: count objects per label and show it top-right."""
        detections = data.get("detections") if isinstance(data, dict) else None
        if detections is None:
            return
        counts: dict[str, int] = {}
        for det in detections:
            counts[det["label"]] = counts.get(det["label"], 0) + 1
        await self.bus.publish(f"display.{self.drone1.drone_id}", counts or {"YOLO": "nothing found"})

    async def end_run(self) -> None:
        self.bus.unsubscribe(f"data.stream.{self.drone1.drone_id}", self._on_detections)
        await self.shutdown_drone(self.drone1)
        if self.video1.is_running:
            await self.video1.stop_recording()
            await self.video1.stop_stream()
        await self.controller.stop_controller()
        self.recorder.detach(self.bus)
