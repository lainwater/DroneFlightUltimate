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
        self.is_turned_on = True

    def _turn_off_controller_without_killing(self):
        self.is_turned_on = False

    def _turn_on_controller_after_starting(self):
        self.is_turned_on = True

    def _cmd_topic(self, target: str | None) -> str:
        """Layout entry's optional "target" -> bus topic. Default 'drone' = cmd.{id}."""
        if target in (None, "drone"):
            return f"cmd.{self.drone_id}"
        if target == "stream":
            return f"cmd.stream.{self.drone_id}"
        raise ValueError(f"Unknown target {target!r} in layout {self.layout!r}")

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
