"""
# feature_aruco - detect + localize ArUco markers, undistorted video

## You need
    A DJI Tello. Default ip 192.168.10.1 = PC on the Tello's own hotspot.
    Tello on your network (station mode)? Put its ip in config/mydrone.json
    (set it up with: python -m tools.set_tello_wifi --help).
    Printed ArUco markers (dictionary + black-square size in [video], defaults.toml).

## Run
    python run.py run -e -n feature_aruco

## Config
    config/mydrone.json     which drone: drone_type, drone_id, ip, ...
    config/defaults.toml    controller layout
                            [video] calibration (+ ArUco settings), see core/video/calibration

## What it shows
    Starts ArUco detection + undistortion; the closest marker's position relative to
    the camera (x right, y down, z forward, metres) is drawn top-right.
    Keys: 5/6 ArUco on/off, 7/8 undistort on/off.
    Without a Tello: set drone_type "sim_simdrone" (+ "port": "6767") in mydrone.json and
    calibration = "webcam" in defaults.toml - then your laptop camera is used.
    New camera? python -m tools.calibration --help
"""

import asyncio

from core.controller import ControllerType, get_controller
from core.logger import LoggerType, get_logger
from core.video import VideoOutputType, get_videostream
from projects.base import ProjectBase


class feature_aruco(ProjectBase):
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

        self.bus.subscribe(f"data.stream.{self.drone1.drone_id}", self._on_aruco)

    async def main(self) -> None:
        await self.controller.start_controller()
        await self.video1.start_stream()
        await self.video1.undistort_on()
        await self.video1.start_aruco()  # dictionary / marker size / publish from [video] in defaults.toml
        print(self.controller.controls_text())
        await asyncio.Event().wait()  # runs until CTRL+C, then end_run()

    async def _on_aruco(self, topic: str, data: dict) -> None:
        """data.stream.<id> carries {"aruco": [...]} (and {"detections": [...]} if YOLO publishes too).
        Here: show the closest marker top-right. Use it for your own logic (e.g. fly to it)."""
        markers = data.get("aruco") if isinstance(data, dict) else None
        if markers is None:
            return
        located = [m for m in markers if "distance" in m]
        if not located:
            text = "no marker" if not markers else f"{len(markers)} marker, no pose (calibration?)"
            await self.bus.publish(f"display.{self.drone1.drone_id}", {"ArUco": text})
            return
        m = min(located, key=lambda m: m["distance"])
        await self.bus.publish(
            f"display.{self.drone1.drone_id}",
            {
                "closest marker": m["id"],
                "x y z [m]": f"{m['x']:.2f} {m['y']:.2f} {m['z']:.2f}",
                "distance [m]": round(m["distance"], 2),
                "r p y [deg]": f"{m['roll']:.0f} {m['pitch']:.0f} {m['yaw']:.0f}",
            },
        )

    async def end_run(self) -> None:
        self.bus.unsubscribe(f"data.stream.{self.drone1.drone_id}", self._on_aruco)
        await self.shutdown_drone(self.drone1)
        if self.video1.is_running:
            await self.video1.stop_recording()
            await self.video1.stop_stream()
        await self.controller.stop_controller()
        self.recorder.detach(self.bus)
