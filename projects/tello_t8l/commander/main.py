"""
tello_t8l - fly a real DJI/Ryze Tello with the RadioMaster T8L (or any
pygame-recognized joystick, via a different `layout` profile).

No auto-connect/auto-arm on startup, on purpose - flip switch SB up to
connect, SA to arm, SC up to take off (see t8l.json for the full
mapping).
"""

import asyncio

from projects.base import ProjectBase
from core.logger import LogLevel
from core.controller import ControllerType, get_controller
from core.drone import DroneType, get_drone


class tello_t8l(ProjectBase):
    async def setup(self) -> None:
        self.recorder.attach(self.bus)
        self.bus.subscribe("*", lambda topic, data: self.live_logger.log(LogLevel.INFO, f"{topic}: {data}"))

        drone_type = DroneType[self.drone_config["drone_1"]["drone_type"].upper()]
        self.drone = get_drone(drone_type, self.drone_config["drone_1"]["drone_id"], bus=self.bus, ip=self.drone_config["drone_1"]["ip"])

        layout = self.app_config.get("controller", {}).get("layout") or None
        self.controller = get_controller(ControllerType.JOYSTICK, drone_id=self.drone_config["drone_1"]["drone_id"], bus=self.bus, layout=layout)

    async def main(self) -> None:
        await self.controller.start_controller()
        print(
            f"T8L controller active for '{self.drone.drone_id}'.\n"
            "SB up = connect, SA down = arm, SC up = take off.\n"
            "Press Ctrl+C to stop."
        )
        await asyncio.Event().wait()

    async def end_run(self) -> None:
        if self.drone.flight_state.value == "inair":
            await self.drone.land()
        if self.drone.con_state.value == "connected":
            await self.drone.disconnect()
        await self.controller.stop_controller()
        self.recorder.detach(self.bus)
        self.drone.detach()