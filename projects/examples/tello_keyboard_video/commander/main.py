"""
# tello_keyboard_video - fly a real DJI Tello with the RadioMaster T8L with video/stream function on.
"""

import asyncio

from core.controller import ControllerType, get_controller
from core.drone import DroneType, get_drone
from core.logger import LoggerType, LogLevel, get_logger
from core.video import VideoOutputType, get_videostream
from projects.base import ProjectBase

qwertz_startup = """
QWERTZ KEYBOARD CONTROLS

# Util
C           = connect
V/B         = arm / disarm
Z/U         = get position / attitude
I/O         = start/stop state receiver
J/K         = start/stop video stream from drone
1/2         = Camera 1/Camera 2 (requires Tello EDU)

# Movement Util
T/L         = takeoff / land
Space       = emergency

# Movement
W/S         = up / down
A/D         = left / right yaw
Up/Down     = forward / backward
Left/Right  = left / right move

# Video
Y/X         = start/stop video stream output
F/G         = on/off FPV mode
N/M         = on/off display stats on video
E/R         = start/stop recording
Q           = take snapshot
"""


class tello_keyboard_video(ProjectBase):
    async def setup(self) -> None:
        self.live_logger = get_logger(LoggerType.LIVE_CONSOLE, min_level=LogLevel.INFO)

        self.recorder.attach(self.bus)
        self.bus.subscribe("*", self.live_logger.log_bus_event)

        d1_conf = self.drone_config["drone_1"]
        drone_type = DroneType[d1_conf["drone_type"].upper()]
        self.drone1 = get_drone(drone_type, d1_conf["drone_id"], bus=self.bus, ip=d1_conf["ip"])

        self.video1 = get_videostream(VideoOutputType.CV2, drone_id=d1_conf["drone_id"], bus=self.bus, media_dir=self.log_dir / "media")

        layout = self.app_config.get("controller", {}).get("layout") or None
        self.controller = get_controller(ControllerType.KEYBOARD, drone_id=d1_conf["drone_id"], bus=self.bus, layout=layout)

    async def main(self) -> None:
        await self.controller.start_controller()
        await self.video1.start_stream()
        print(qwertz_startup)
        await asyncio.Event().wait()

    async def end_run(self) -> None:
        if self.drone1.video_streaming:
            await self.drone1.stop_video()
        if self.drone1.flight_state.value == "inair":
            await self.drone1.land()
        if self.drone1.con_state.value == "connected":
            await self.drone1.disconnect()
        if self.video1.is_running:
            await self.video1.stop_stream()
        await self.controller.stop_controller()
        self.recorder.detach(self.bus)
        self.drone1.detach()
