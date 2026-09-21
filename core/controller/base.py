"""
ControllerBase - Interface for drone operations.
"""

from abc import ABC, abstractmethod

from core.fileops import get_fileops


class ControllerBase(ABC):
    def __init__(self, drone_id: str, bus: object, layout: str):
        self.fops = get_fileops()
        self.config = None
        self.drone_id = drone_id
        self.layout = layout
        self.bus = bus
        self._load_layout(layout)

        self.is_running = False

    @abstractmethod
    def _load_layout(self, layout: str = None):
        """Load the layout."""
        raise NotImplementedError

    @abstractmethod
    async def _publish_parser(self, data: dict) -> None:
        """Parses controller input to bus publish"""
        raise NotImplementedError

    @abstractmethod
    async def start_controller(self) -> None:
        """Start the controller."""
        raise NotImplementedError

    @abstractmethod
    async def stop_controller(self) -> None:
        """Stop the controller"""
        raise NotImplementedError
