"""
ProjectBase - Base object of any project
"""

import asyncio
import tomllib
from pathlib import Path
from abc import ABC, abstractmethod

from core.bus import get_bus
from core.fileops import get_fileops
from core.logger import LogLevel, LoggerType, get_logger
from core.bus_player_recorder import get_recorder


class ProjectBase(ABC):
    def __init__(self, root_path: Path = Path(__file__).resolve(), **kwargs):
        self.root_path = root_path
        self.fops = get_fileops()
        self.bus = get_bus()
        self.debug_logger = get_logger(
                LoggerType.RECORD,
                min_level=LogLevel[self.app_config.get("logging", {}).get("level", "INFO")],
                log_path=self.root_path / "logs" / "debug_logs" / "session.jsonl",
            )
        self.live_logger = get_logger(LoggerType.LIVE_CONSOLE, min_level=LogLevel.INFO)
        self.recorder = get_recorder(self.root_path / "logs" / "bus_logs" / "flight.jsonl")
        
        self.drone_config = None
        self.app_config = self.load_drone_config(root_path)

    def load_app_config(self) -> dict:
        """Load app config. Default path will be used if none provided."""
        path = self.root_path / "config" / "app_config" / "defaults.toml"
        return self.fops.read_toml(path)

    def load_drone_config(self) -> dict:
        """Load drone config"""
        path = self.root_path / "config" / "drone_config" / "mydrone.json"
        return self.drone_config = self.fops.read_toml(path)

    async def run(self) -> None:
        """Run the projects setup and main"""
        try:
            await self.setup()
            asyncio.run(self.main())
            try:
                self.end_run()
            except:
                pass
        except KeyboardInterrupt:
            try:
                self.end_run()
            except:
                pass
            print("\nStopped by Keyboard Interrupt (CTRL+C).")
    
    @abstractmethod
    async def setup(self) -> None:
        raise NotImplementedError
    
    @abstractmethod
    async def main(self) -> None:
            raise NotImplementedError
    
    @abstractmethod
    async def end_run(self) -> None:
        raise NotImplementedError