"""
ProjectBase - shared lifecycle and wiring for every DroneFlightUltimate
example/project.

Config loading, bus, loggers, and the bus recorder are all set up once
here, so a concrete project only has to implement three things:
    setup()   - wire up drone/controller/etc (called once)
    main()    - the actual run loop
    end_run() - cleanup (always called by run(), no matter how main()
                ended - normal return, exception, or Ctrl+C)
"""

import asyncio
from abc import ABC, abstractmethod
from pathlib import Path

from core.bus import get_bus
from core.bus_player_recorder import get_recorder
from core.fileops import get_fileops
from core.logger import LogLevel, LoggerType, get_logger


class ProjectBase(ABC):
    def __init__(self, root_path: Path, **kwargs):
        self.root_path = Path(root_path)
        self.fops = get_fileops()

        self.app_config = self.load_app_config()
        self.drone_config = self.load_drone_config()

        self.bus = get_bus()
        self.debug_logger = get_logger(
            LoggerType.RECORD,
            min_level=LogLevel[self.app_config.get("logging", {}).get("level", "INFO")],
            log_path=self.root_path / "logs" / "debug_logs" / "session.jsonl",
        )
        self.live_logger = get_logger(LoggerType.LIVE_CONSOLE, min_level=LogLevel.INFO)
        self.recorder = get_recorder(self.root_path / "logs" / "bus_logs" / "flight.jsonl")

    def load_app_config(self) -> dict:
        """Load this project's app-level config (logging level, keyboard
        layout override, ...)."""
        path = self.root_path / "config" / "app_config" / "defaults.toml"
        return self.fops.read_toml(path)

    def load_drone_config(self) -> dict:
        """Load this project's drone config (drone_type, drone_id, ip, ...).
        This is JSON, not TOML - read_json, not read_toml."""
        path = self.root_path / "config" / "drone_config" / "mydrone.json"
        return self.fops.read_json(path)

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
        """Clean up: detach recorder/drone/controller, write a final
        log entry. Always called by run(), even on error or interrupt."""
        raise NotImplementedError