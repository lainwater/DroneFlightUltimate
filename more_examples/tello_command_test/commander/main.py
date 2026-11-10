"""
# tello_command_test - step through the Tello commands one by one

## You need
    Any Tello. Set "model" in config/mydrone.json (tello / tello_edu / tello_talent): commands
    your model can't do are skipped (you see why). Without "model" everything is sent.

## Run
    python run.py run -m -n tello_command_test

## What it does
    Sends every command by its commands.json name (the same way a controller does) and
    waits PAUSE_S between them. Every command should get an ack (or data for get_*).

    [test] fly = false   ground commands only (readings, LED, dot matrix, motor on/off)
    [test] fly = true    also takes off and tests flight commands - give it about
                         2 x 2 m of free space and 1.5 m of height!
"""

import asyncio

from core.logger import LoggerType, get_logger
from projects.base import ProjectBase

PAUSE_S = 2.0

GROUND_STEPS = [
    ("get_battery", {}),
    ("get_height", {}),
    ("get_temperature", {}),
    ("get_attitude", {}),
    ("get_tof", {}),
    ("get_sdk_version", {}),  # EDU / Talent
    ("get_serial_number", {}),
    ("get_hardware", {}),  # TELLO or RMTT
    ("get_ext_version", {}),  # Talent (expansion kit) from here
    ("get_ext_tof", {}),
    ("ext_led", {"r": 255, "g": 0, "b": 0}),
    ("ext_led_pulse", {}),
    ("ext_led_blink", {}),
    ("ext_led_off", {}),
    ("ext_matrix_brightness", {"level": 100}),
    ("ext_matrix_show", {"text": "heart"}),
    ("ext_matrix_pattern", {}),  # smiley
    ("ext_matrix_scroll_text", {"text": "HI"}),
    ("ext_matrix_clear", {}),
    ("motor_on", {}),  # EDU (new firmware) / Talent
    ("motor_off", {}),
]

FLIGHT_STEPS = [
    ("takeoff", {}),
    ("rotate_cw", {"degrees": 90}),
    ("rotate_ccw", {"degrees": 90}),
    ("steps_move_up", {"distance": 30}),
    ("goto", {"x": 50, "y": 0, "z": 0, "speed": 30}),  # 50 cm forward
    ("goto", {"x": -50, "y": 0, "z": 0, "speed": 30}),  # and back
    ("curve", {}),
    ("stop", {}),  # EDU / Talent
    # ("flip_forward", {}),  # only with > 50 % battery and lots of room
    ("land", {}),
]


def runnable_steps(steps: list[tuple[str, dict]], command_map: dict, model: str | None) -> tuple[list, list]:
    """-> (steps this model can do, [(action, needed models)] that are skipped)."""
    ok, skipped = [], []
    for action, args in steps:
        models = command_map.get(action, {}).get("models")
        if model and models and model not in models:
            skipped.append((action, models))
        else:
            ok.append((action, args))
    return ok, skipped


class tello_command_test(ProjectBase):
    async def setup(self) -> None:
        self.live_logger = get_logger(LoggerType.LIVE_CONSOLE, min_level=self.log_level)
        self.recorder.attach(self.bus)
        self.bus.subscribe("*", self.live_logger.log_bus_event)
        self.drone1 = self.create_drone("drone_1")
        self.fly = bool(self.app_config.get("test", {}).get("fly", False))

    async def main(self) -> None:
        await self.send("connect")
        await self.send("set_arm")

        steps, skipped = runnable_steps(GROUND_STEPS + (FLIGHT_STEPS if self.fly else []), self.drone1.command_map, self.drone1.model)
        for action, models in skipped:
            print(f"skip {action:<24} needs {' / '.join(models)} (this is a {self.drone1.model})")
        for i, (action, args) in enumerate(steps, start=1):
            print(f"\n--- [{i}/{len(steps)}] {action} {args or ''}")
            await self.send(action, args)
            await asyncio.sleep(PAUSE_S)

        print("\nAll commands sent. CTRL+C to quit.")
        await asyncio.Event().wait()

    async def send(self, action: str, args: dict | None = None) -> None:
        await self.bus.publish(f"cmd.{self.drone1.drone_id}", {"action": action, "args": args or {}})

    async def end_run(self) -> None:
        await self.shutdown_drone(self.drone1)
        self.recorder.detach(self.bus)
