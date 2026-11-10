"""
# talent_cooling_battery_gauge - automatic cooling + battery gauge on the dot matrix

## You need
    Tello Talent (RoboMaster TT) with the expansion kit (default firmware). Drone stays on the ground.

## Run
    python run.py run -m -n talent_cooling_battery_gauge

## What it does
    Listens to the telemetry (state.<id>, ~10 per second):
        temperature > COOL_ON_C   -> motor_on  (props spin slowly to cool the board - no takeoff)
        temperature < COOL_OFF_C  -> motor_off
        battery                   -> one column of the 8x8 matrix as a fuel gauge (bottom = empty)
"""

import asyncio

from core.logger import LoggerType, get_logger
from projects.base import ProjectBase

COOL_ON_C = 74  # start cooling above this board temperature
COOL_OFF_C = 60  # stop cooling below this
GAUGE_COLUMN = 0  # matrix column for the battery (0 = left)
LOW_BATTERY = 25  # below this % the gauge turns red
GAUGE_COLOR = "b"  # r = red, b = blue, p = purple


def battery_pattern(percent: float, column: int = GAUGE_COLUMN, color: str = GAUGE_COLOR, low: float = LOW_BATTERY) -> str:
    """64-char matrix pattern (row by row, top first), one column filled from the
    bottom: 8 LEDs = 100 %. At least 1 LED while there is any charge."""
    leds = min(8, max(1 if percent > 0 else 0, round(percent / 100 * 8)))
    c = "r" if percent < low else color
    rows = []
    for row in range(8):  # row 0 = top
        line = ["0"] * 8
        if row >= 8 - leds:
            line[column] = c
        rows.append("".join(line))
    return "".join(rows)


class talent_cooling_battery_gauge(ProjectBase):
    async def setup(self) -> None:
        self.live_logger = get_logger(LoggerType.LIVE_CONSOLE, min_level=self.log_level, exclude_topics=("frame.*", "state.*"))
        self.recorder.attach(self.bus)
        self.bus.subscribe("*", self.live_logger.log_bus_event)

        self.drone1 = self.create_drone("drone_1")
        self.drone_id = self.drone1.drone_id
        self.cooling = False
        self.shown_pattern = None  # only resend when a LED changes, not 10x per second
        self.bus.subscribe(f"state.{self.drone_id}", self.on_state)

    async def main(self) -> None:
        await self.send("connect")
        await self.send("set_arm")  # motor_on needs the drone armed (software safety gate)
        await self.send("start_state_receiver")
        print(f"\nCooling: motors on above {COOL_ON_C} C, off below {COOL_OFF_C} C. CTRL+C to quit.")
        await asyncio.Event().wait()

    async def on_state(self, topic: str, data: dict) -> None:
        await self.check_cooling(data.get("temperature"))
        await self.show_battery(data.get("battery"))

    async def check_cooling(self, temp: float | None) -> None:
        if temp is None:
            return
        if not self.cooling and temp > COOL_ON_C:
            print(f"board {temp} C > {COOL_ON_C} C: cooling ON")
            self.cooling = True
            await self.send("motor_on")
        elif self.cooling and temp < COOL_OFF_C:
            print(f"board {temp} C < {COOL_OFF_C} C: cooling OFF")
            self.cooling = False
            await self.send("motor_off")

    async def show_battery(self, percent: float | None) -> None:
        if percent is None:
            return
        pattern = battery_pattern(percent)
        if pattern != self.shown_pattern:
            self.shown_pattern = pattern
            await self.send("ext_matrix_pattern", {"pattern": pattern})

    async def end_run(self) -> None:
        self.bus.unsubscribe(f"state.{self.drone_id}", self.on_state)
        if self.drone1.con_state.value == "connected":
            if self.cooling:
                await self.send("motor_off")
            await self.send("ext_matrix_clear")
        await self.shutdown_drone(self.drone1)
        self.recorder.detach(self.bus)

    async def send(self, action: str, args: dict | None = None) -> None:
        await self.bus.publish(f"cmd.{self.drone_id}", {"action": action, "args": args or {}})
