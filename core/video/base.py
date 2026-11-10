"""
VideoBase - Output frames from Bus
"""

from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any

from core.fileops import get_fileops
from core.video.record_vid import FrameRecorder
from core.video.snapshot import save_snapshot


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
        self.data_to_display: tuple = ("ts", "fps", "battery", "height")  # keys of the unified telemetry
        self.state_data = {}

        # Second overlay block: free data sent by a project (e.g. results of your
        # own calculations), drawn top-right. See _on_display_event().
        self.display_custom_data = True
        self.custom_data: dict = {}

        self.fops = get_fileops()
        self.command_map = self._initialize_command_map()

        self.media_dir = Path(kwargs.get("media_dir", Path.cwd() / "logs" / "media"))
        self.recorder = FrameRecorder(self.media_dir, drone_id)
        self._latest_frame = None

    def _initialize_command_map(self) -> dict:
        """Initialize the command map for the stream."""
        return self.fops.read_json(self.config_dir / "commands.json")

    def _attach(self) -> None:
        """Start recording every 'cmd.stream.{self.drone_id}', 'frame.{self.drone_id}' and 'state.{self.drone_id}' event published on `bus`.
        Called by start_stream()"""
        self.bus.subscribe(f"frame.{self.drone_id}", self._on_frame_event)
        self.bus.subscribe(f"cmd.stream.{self.drone_id}", self._on_cmd_event)
        self.bus.subscribe(f"state.{self.drone_id}", self._on_state_event)
        self.bus.subscribe(f"display.{self.drone_id}", self._on_display_event)

    def _detach(self) -> None:
        """Stop recording events from `bus`. Safe to call even if never attached.
        Called by stop_stream()"""
        self.bus.unsubscribe(f"frame.{self.drone_id}", self._on_frame_event)
        self.bus.unsubscribe(f"cmd.stream.{self.drone_id}", self._on_cmd_event)
        self.bus.unsubscribe(f"state.{self.drone_id}", self._on_state_event)
        self.bus.unsubscribe(f"display.{self.drone_id}", self._on_display_event)

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

    async def _on_display_event(self, topic: str, data: Any):
        """
        Custom overlay data from a project - the video module only DRAWS it,
        all calculations stay in your project.
        Contract of topic, data
            display.drone_id  - {"label": value, ...}
                value may be anything: number, string, list, numpy array/matrix
                (multi-line values are drawn over several lines)
            Every message REPLACES the previous block; publish {} to clear it.
        Example (in your project's main):
            await self.bus.publish("display.drone1", {"R": rot_matrix, "dist": 1.23})
        """
        if data is None:
            data = {}
        if not isinstance(data, dict):
            data = {"data": data}
        self.custom_data = dict(data)

    def _custom_data_lines(self) -> list[str]:
        """custom_data -> text lines ("label: value"; matrices get one line per row)."""
        lines: list[str] = []
        for label, value in self.custom_data.items():
            text = self._format_value(value).splitlines() or [""]
            lines.append(f"{label}: {text[0]}")
            indent = " " * (len(str(label)) + 2)
            lines.extend(indent + row for row in text[1:])
        return lines

    @staticmethod
    def _format_value(value: Any) -> str:
        if hasattr(value, "shape") and hasattr(value, "tolist"):  # numpy array / matrix -> same as a list
            value = value.tolist()
            if not isinstance(value, list):  # 0-d array = single number
                return VideoBase._format_value(value)
            if value and not isinstance(value[0], list):  # 1-d vector -> one row
                value = [value]
        if isinstance(value, dict):  # e.g. attitude {"pitch": 0, "roll": 1, "yaw": 90} -> "pitch 0, roll 1, yaw 90"
            return ", ".join(f"{k} {VideoBase._format_value(v)}" for k, v in value.items())
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        if isinstance(value, (list, tuple)) and value and all(isinstance(row, (list, tuple)) for row in value):
            # plain list of lists = matrix: one row per line, columns aligned
            cells = [[VideoBase._format_value(v) for v in row] for row in value]
            width = max(len(c) for row in cells for c in row)
            return "\n".join("[ " + "  ".join(c.rjust(width) for c in row) + " ]" for row in cells)
        if isinstance(value, float):
            return f"{value:.2f}"
        return str(value)

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

    async def turn_on_display_state_data(self, data_to_display: tuple = ("ts", "fps", "battery", "height")):
        """Turn on the display of state data"""
        self.data_to_display = data_to_display
        self.display_state_data = True

    async def turn_off_display_state_data(self):
        """Turn off the display of state data"""
        self.display_state_data = False

    async def set_custom_data(self, data: dict | None = None):
        """Same as publishing on display.{drone_id} - for use via cmd.stream."""
        await self._on_display_event(f"display.{self.drone_id}", data or {})

    async def clear_custom_data(self):
        self.custom_data = {}

    async def turn_on_display_custom_data(self):
        """Show the custom (project) data block"""
        self.display_custom_data = True

    async def turn_off_display_custom_data(self):
        """Hide the custom (project) data block (data is kept)"""
        self.display_custom_data = False

    async def start_recording(self):
        if self._latest_frame is None:
            await self._publish_parser("error", {"error": "NoFrame", "message": "No frame received yet."})
            return
        path = self.recorder.start(self._latest_frame)
        await self._publish_parser("ack", {"cmd": "start_recording", "ack": "True", "path": str(path)})

    async def stop_recording(self):
        path = self.recorder.stop()
        await self._publish_parser("ack", {"cmd": "stop_recording", "ack": "True", "path": str(path) if path else None})

    async def take_snapshot(self):
        if self._latest_frame is None:
            await self._publish_parser("error", {"error": "NoFrame", "message": "No frame received yet."})
            return
        path = save_snapshot(self._latest_frame, self.media_dir, self.drone_id)
        await self._publish_parser("ack", {"cmd": "take_snapshot", "ack": "True", "path": str(path)})

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
