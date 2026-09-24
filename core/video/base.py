"""
VideoBase - Output frames from Bus
"""

from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any

from core.fileops import get_fileops


class VideoBase(ABC):
    def __init__(self, drone_id: str, bus: object, **kwargs):
        self.drone_id = drone_id
        self.bus = bus
        self.init_kwargs = kwargs

        self.is_running = False
        self.fpv_goggles_mode = False
        self.display_state_data = False
        self.rescale_factor = 1
        self.ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.data_to_display: tuple = ("ts", "fpsbat", "pos")
        self.state_data = {}

        self.fops = get_fileops()
        self.command_map = self._initialize_command_map()

    def _initialize_command_map(self) -> dict:
        """Initialize the command map for the stream."""
        return self.fops.read_json(self.config_dir / "commands.json")

    def _attach(self) -> None:
        """Start recording every 'cmd.stream.{self.drone_id}', 'frame.{self.drone_id}' and 'state.{self.drone_id}' event published on `bus`.
        Called by start_stream()"""
        self.bus.subscribe(f"frame.{self.drone_id}", self._on_frame_event)
        self.bus.subscribe(f"cmd.stream.{self.drone_id}", self._on_cmd_event)
        self.bus.subscribe(f"state.{self.drone_id}", self._on_state_event)

    def _detach(self) -> None:
        """Stop recording events from `bus`. Safe to call even if never attached.
        Called by stop_stream()"""
        self.bus.unsubscribe(f"frame.{self.drone_id}", self._on_frame_event)
        self.bus.unsubscribe(f"cmd.stream.{self.drone_id}", self._on_cmd_event)
        self.bus.unsubscribe(f"state.{self.drone_id}", self._on_state_event)

    async def _on_frame_event(self, topic: str, data: Any):
        """
        What happens on frame event from bus
        Contract of topic, data
            frame.drone_id  - {"ts": 1758705600.1, "seq": 4821, "encoding": "bgr24", "frame": "<numpy BGR ndarray>"}
        """
        if not self.is_running:
            return
        if (not data) or (data is None) or (data == {}):
            return
        self.ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            await self._update_frame(data)
        except Exception as e:
            await self._publish_parser("error", {"error": type(e).__name__, "message": str(e)})

    async def _on_cmd_event(self, topic: str, data: Any):
        if not self.is_running:
            return
        if (not data) or (data is None) or (data == {}):
            return
        action = data.get("action")
        if not action:
            await self._publish_parser("error", {"error": "missing_action", "message": f"No action specified in data: {data}"})
            return
        kwargs = data.get("args", {})
        try:
            await self._execute(action, **kwargs)
        except Exception as e:
            await self._publish_parser("error", {"error": type(e).__name__, "message": str(e), "action": action})

    async def _on_state_event(self, topic: str, data: Any):
        if not self.is_running:
            return
        if (not data) or (data is None) or (data == {}):
            return
        self.state_data = data

    async def _execute(self, action: str, **kwargs) -> None:
        if action not in self.command_map:
            await self._publish_parser("error", {"error": "NotCapable", "message": f"'{action}' not in stream.{self.drone_id}'s capabilities"})
            return
        entry = self.command_map[action]
        method_name = entry["method"]
        method = getattr(self, method_name, None)
        if method is None:
            await self._publish_parser(
                "error", {"error": "NoSuchMethod", "message": f"'{action}' maps to '{method_name}', but stream.{self.drone_id} has no such method"}
            )
            return

        kwargs = {**entry.get("args", {}), **kwargs}
        try:
            await method(**kwargs)
        except Exception as exc:
            await self._publish_parser("error", {"error": type(exc).__name__, "message": str(exc), "action": action})

    async def _publish_parser(self, topic: str, data: dict) -> None:
        """Publish to the bus."""
        if self.bus:
            await self.bus.publish(f"{topic}.stream.{self.drone_id}", data)

    async def set_rescale_factor(self, scale):
        """Set how by how much frame will be resized"""
        self.rescale_factor = scale

    async def turn_on_fpv_goggles(self):
        """Turn on the FPV-Goggles mode"""
        self.fpv_goggles_mode = True

    async def turn_off_fpv_goggles(self):
        """Turn off the FPV-Goggles mode"""
        self.fpv_goggles_mode = False

    async def turn_on_display_state_data(self, data_to_display: tuple = ("ts", "fps", "bat", "pos")):
        """Turn on the display of state data"""
        self.data_to_display = data_to_display
        self.display_state_data = True

    async def turn_off_display_state_data(self):
        """Turn off the display of state data"""
        self.display_state_data = False

    @property
    @abstractmethod
    def config_dir(self) -> Path:
        """Directory containing this streams's commands.json
        Concrete implementations return Path(__file__).parent so this
        works no matter where the app was launched from."""
        raise NotImplementedError

    @abstractmethod
    async def start_stream(self):
        """Start the video stream."""
        raise NotImplementedError

    @abstractmethod
    async def stop_stream(self):
        """Stop the video stream."""
        raise NotImplementedError

    @abstractmethod
    async def _update_frame(self, data):
        """Update displayed frame"""
        raise NotImplementedError

    @abstractmethod
    async def _rescale_frame(self, frame, scale):
        """Rescale the frame"""
        raise NotImplementedError

    @abstractmethod
    async def _to_fpv_goggles_frame(self, frame):
        """Duplicate the frame side-by-side for FPV goggles."""
        raise NotImplementedError

    @abstractmethod
    async def _display_text(self, text, position, font, font_scale, color, thickness):
        """Render text on frame"""
        raise NotImplementedError

    @abstractmethod
    async def _data_to_frame(self, data):
        """Turn a frame.{drone_id} bus message into a implementation format frame."""
        raise NotImplementedError
