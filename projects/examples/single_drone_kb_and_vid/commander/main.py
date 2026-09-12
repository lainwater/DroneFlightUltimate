"""
single_drone_kb_and_vid - minimal example wiring one drone to a
keyboard controller, with full flight logging. Video comes later once
core/video exists.

Run from the project root (relies on the editable install from
`pip install -e ".[dev]"`, so `core` is importable regardless of CWD):
    python projects/examples/single_drone_kb_and_vid/commander/main.py
"""

import asyncio
import tomllib
from pathlib import Path

from core.bus import get_bus
from core.controller import ControllerType, get_controller
from core.drone import DroneType, get_drone
from core.fileops import get_fileops
from core.logger import LogLevel, LoggerType, get_logger
from core.bus_player_recorder.implementations.jsonl.bus_recorder import BusRecorder

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def load_app_config() -> dict:
    path = PROJECT_ROOT / "config" / "app_config" / "defaults.toml"
    with open(path, "rb") as f:
        return tomllib.load(f)


def load_drone_config() -> dict:
    fops = get_fileops()
    path = PROJECT_ROOT / "config" / "drone_config" / "mydrone.json"
    return fops.read_json(path)


async def main() -> None:
    app_config = load_app_config()
    drone_config = load_drone_config()

    bus = get_bus()

    # Ebene B: classic debug log for this session, written to disk.
    debug_logger = get_logger(
        LoggerType.RECORD,
        min_level=LogLevel[app_config.get("logging", {}).get("level", "INFO")],
        log_path=PROJECT_ROOT / "logs" / "debug_logs" / "session.jsonl",
    )
    # Also print a live feed of every bus event to the console, so you
    # can actually see acks/state/errors while flying.
    live_logger = get_logger(LoggerType.LIVE_CONSOLE, min_level=LogLevel.INFO)
    bus.subscribe("*", lambda topic, data: live_logger.log(LogLevel.INFO, f"{topic}: {data}"))

    # Ebene A: full flight recording for later replay via core.player.
    recorder = BusRecorder(PROJECT_ROOT / "logs" / "bus_logs" / "flight.jsonl")
    recorder.attach(bus)

    drone_type = DroneType[drone_config["drone_type"].upper()]
    drone = get_drone(
        drone_type,
        drone_config["drone_id"],
        bus=bus,
        ip=drone_config["ip"],
    )

    layout = app_config.get("keyboard", {}).get("layout") or None
    controller = get_controller(
        ControllerType.KEYBOARD_CONTROLLER,
        drone_id=drone_config["drone_id"],
        bus=bus,
        layout=layout,
    )

    debug_logger.log(LogLevel.INFO, "Session starting", drone_id=drone.drone_id)
    await controller.start_controller()

    print(f"Keyboard controller active for '{drone.drone_id}'. Press Ctrl+C to stop.")
    try:
        await asyncio.Event().wait()  # keep the event loop alive until interrupted
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        debug_logger.log(LogLevel.INFO, "Session ending", drone_id=drone.drone_id)
        # TODO: once KeyboardController has a stop_controller(), call it
        # here too (kb_listener.stop()) for a fully clean shutdown.
        recorder.detach(bus)
        drone.detach()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped.")