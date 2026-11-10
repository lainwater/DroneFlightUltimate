"""
# talent_tof_ruler - the expansion kit's distance sensor as a ruler on the dot matrix

## You need
    Tello Talent (RoboMaster TT) with the expansion kit. Drone stays on the ground.

## Run
    python run.py run -m -n talent_tof_ruler

## What it does
    Every READ_EVERY_S: get_ext_tof (forward distance sensor) -> scrolls "123cm" over the matrix.
    The answer arrives on data.<id> as {"ext_tof": cm} (unified units, see core/drone/telemetry.py).
"""

import asyncio

from core.logger import LoggerType, get_logger
from projects.base import ProjectBase

READ_EVERY_S = 7.0  # the text needs time to scroll through before the next one replaces it
OUT_OF_RANGE_CM = 819  # the sensor answers 8192 mm (= 819.2 cm) when nothing is in range


def ruler_text(cm: float) -> str:
    """Distance -> text for the matrix ('--' = nothing in range)."""
    return "--" if cm >= OUT_OF_RANGE_CM else f"{round(cm)}cm"


class talent_tof_ruler(ProjectBase):
    async def setup(self) -> None:
        self.live_logger = get_logger(LoggerType.LIVE_CONSOLE, min_level=self.log_level)
        self.recorder.attach(self.bus)
        self.bus.subscribe("*", self.live_logger.log_bus_event)

        self.drone1 = self.create_drone("drone_1")
        self.drone_id = self.drone1.drone_id
        self.bus.subscribe(f"data.{self.drone_id}", self.on_data)

    async def main(self) -> None:
        await self.send("connect")
        while True:  # until CTRL+C
            await self.send("get_ext_tof")
            await asyncio.sleep(READ_EVERY_S)

    async def on_data(self, topic: str, data: dict) -> None:
        if "ext_tof" in data and isinstance(data["ext_tof"], (int, float)):
            await self.send("ext_matrix_scroll_text", {"text": ruler_text(data["ext_tof"])})

    async def end_run(self) -> None:
        self.bus.unsubscribe(f"data.{self.drone_id}", self.on_data)
        if self.drone1.con_state.value == "connected":
            await self.send("ext_matrix_clear")
        await self.shutdown_drone(self.drone1)
        self.recorder.detach(self.bus)

    async def send(self, action: str, args: dict | None = None) -> None:
        await self.bus.publish(f"cmd.{self.drone_id}", {"action": action, "args": args or {}})
