"""
# feature_vicon - Tello pose from the Vicon motion capture system, drawn on the video

## You need
    A Tello on the Vicon lab network (ip in config/mydrone.json) and the Vicon
    DataStream SDK python wrapper (vicon_dssdk, installed from the Vicon SDK folder).

## Run
    python run.py run -e -n feature_vicon

## Config
    config/mydrone.json     which drone: drone_type, drone_id, ip, ...
    config/defaults.toml    controller layout
                            [video] calibration (+ ArUco settings), see core/video/calibration

## What it shows
    core.vicon reads one Vicon subject ([vicon] in defaults.toml) in a thread and publishes
    vicon.<drone_id> (20 Hz, newest data only - it never lags behind). Drawn top-right.
"""

import asyncio

from core.controller import ControllerType, get_controller
from core.logger import LoggerType, get_logger
from core.vicon import get_vicon
from core.video import VideoOutputType, get_videostream
from projects.base import ProjectBase


class feature_vicon(ProjectBase):
    async def setup(self) -> None:
        # every bus message -> console (minus the 20-30/s ones), and recorded to logs/bus_logs/
        self.live_logger = get_logger(
            LoggerType.LIVE_CONSOLE, min_level=self.log_level, exclude_topics=("frame.*", "vicon.*", "display.*", "data.stream.*")
        )
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

        # Vicon receiver for drone1 ([vicon] in defaults.toml)
        vicon_conf = self.app_config.get("vicon", {})
        self.vicon = get_vicon(
            drone_id=self.drone1.drone_id,
            bus=self.bus,
            host=vicon_conf.get("host", "192.168.10.1:801"),
            subject=vicon_conf.get("subject", "tello-1"),
            rate_hz=float(vicon_conf.get("rate_hz", 20)),
        )
        self.bus.subscribe(f"vicon.{self.drone1.drone_id}", self._on_vicon)
        # display.* is only the text version of vicon.* - don't write it to disk twice
        self.recorder.exclude_topics = ("frame.*", "display.*")

    async def main(self) -> None:
        await self.controller.start_controller()
        await self.video1.start_stream()
        await self.vicon.start()
        print(self.controller.controls_text())
        await asyncio.Event().wait()  # runs until CTRL+C, then end_run()

    async def _on_vicon(self, topic: str, data: dict) -> None:
        """vicon.<id> -> text block on the video (display.<id>)."""
        if data.get("occluded"):
            display = {"VICON": f"{data.get('subject')}  OCCLUDED / not visible"}
        else:
            display = {
                "VICON": data.get("subject"),
                "x y z [mm]": f"{data['x']:8.1f} {data['y']:8.1f} {data['z']:8.1f}",
                "r p y [deg]": f"{data['roll']:6.1f} {data['pitch']:6.1f} {data['yaw']:6.1f}",
                "frame": data.get("frame"),
            }
        await self.bus.publish(f"display.{self.drone1.drone_id}", display)

    async def end_run(self) -> None:
        await self.vicon.stop()
        self.bus.unsubscribe(f"vicon.{self.drone1.drone_id}", self._on_vicon)
        await self.shutdown_drone(self.drone1)
        if self.video1.is_running:
            await self.video1.stop_recording()
            await self.video1.stop_stream()
        await self.controller.stop_controller()
        self.recorder.detach(self.bus)
