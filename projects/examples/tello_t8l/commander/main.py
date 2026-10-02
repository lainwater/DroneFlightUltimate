"""
# tello_t8l - fly a real DJI Tello with the RadioMaster T8L.
## Instructions:
    Turn on your RadioMaster T8L. Then plug it into your PC via USB.
    Then turn on the Tello and connect to it's WiFi Hotspot.
    Then you can type `python run.py r tello_t8l` in your console to launch this project.

(To connect via your own hotspot. You have to tell the Tello your SSID and Password.
See core/drone/implementations/DJI/tello/tello.py `connect_via_wifi(...)` docstrings for further instructions.)
"""

import asyncio

from core.controller import ControllerType, get_controller
from core.drone import DroneType, get_drone
from core.logger import LoggerType, LogLevel, get_logger
from projects.base import ProjectBase

t8l_startup = """
T8L CONTROLS
Sticks: X/Y/Z/Yaw = RC movement
SA:         negative = arm
SE:         negative = takeoff, positive = land
SB:         down = start state receiver
"""


class tello_t8l(ProjectBase):
    async def setup(self) -> None:
        self.live_logger = get_logger(LoggerType.LIVE_CONSOLE, min_level=LogLevel.INFO)

        self.recorder.attach(self.bus)
        self.bus.subscribe("*", self.live_logger.log_bus_event)

        d1_conf = self.drone_config["drone_1"]
        drone_type = DroneType[d1_conf["drone_type"].upper()]
        self.drone1 = get_drone(drone_type, d1_conf["drone_id"], bus=self.bus, ip=d1_conf["ip"])

        layout = self.app_config.get("controller", {}).get("layout") or None
        self.controller = get_controller(ControllerType.JOYSTICK, drone_id=d1_conf["drone_id"], bus=self.bus, layout=layout)

    async def main(self) -> None:
        await self.controller.start_controller()
        print(t8l_startup)
        await asyncio.Event().wait()

    async def end_run(self) -> None:
        if self.drone1.flight_state.value == "inair":
            await self.drone1.land()
        if self.drone1.con_state.value == "connected":
            await self.drone1.disconnect()
        await self.controller.stop_controller()
        self.recorder.detach(self.bus)
        self.drone1.detach()
