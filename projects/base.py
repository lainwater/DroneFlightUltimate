"""
ProjectBase - shared lifecycle and wiring for every DroneFlightUltimate
example/project.

__init__.py:    ignore

main.py:        where your project lives (setup, main, end_run)

Config:         config/defaults.toml + config/mydrone.json

Logs:           bus_logs/flight_<timestamp>.jsonl, a fresh file every run so old
                sessions are never overwritten.
"""

import asyncio.exceptions
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path

from core.bus import get_bus
from core.bus_player_recorder import get_recorder
from core.fileops import get_fileops


class ProjectBase(ABC):
    def __init__(self, root_path: Path, **kwargs):
        self.root_path = Path(root_path)
        self.kwargs = kwargs

        self.fops = get_fileops()
        self.bus = get_bus()

        self.app_config = self.load_app_config()
        self.drone_config = self.load_drone_config()

        session_stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.recorder = get_recorder(self.log_dir / "bus_logs" / f"flight_{session_stamp}.jsonl")

    @property
    def log_dir(self) -> Path:
        """Where this project's logs are stored."""
        return self.root_path / "logs"

    def load_app_config(self) -> dict:
        """Load this project's app-level config (logging level, keyboard/
        joystick layout override, ...)."""
        return self.fops.read_toml(self.root_path / "config" / "defaults.toml")

    def load_drone_config(self) -> dict:
        """Load this project's drone config (drone_type, drone_id, ip, ...)."""
        return self.fops.read_json(self.root_path / "config" / "mydrone.json")

    async def run(self) -> None:
        """Run this project's full lifecycle. Call this once from an
        `asyncio.run(project.run())` at the top level - run() itself
        must NOT call asyncio.run() again, it's already a coroutine
        running inside that event loop."""
        await self.setup()
        try:
            await self.main()
        except KeyboardInterrupt:
            print("\nStopped by Keyboard Interrupt (CTRL+C).")
        except asyncio.exceptions.CancelledError:
            print("\nStopped by asyncio.exceptions.CancelledError (likely triggered by CTRL+C).")
        finally:
            await self.end_run()

    @abstractmethod
    async def setup(self) -> None:
        """Wire up drone, controller, and anything else this project
        needs. Called once, before main()."""
        raise NotImplementedError

    @abstractmethod
    async def main(self) -> None:
        """The actual run loop. Runs until the project is done or the
        user interrupts it - no need to handle cleanup here, run()
        guarantees end_run() fires afterwards regardless."""
        raise NotImplementedError

    @abstractmethod
    async def end_run(self) -> None:
        """Clean up: detach recorder/drone/controller. Always called
        by run(), even on error or interrupt."""
        raise NotImplementedError
