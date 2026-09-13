"""
BusRecorder - subscribes to every event published on the EventBus and
appends each one as a single JSON line, so core.bus_player_recorder's
BusPlayer can replay a whole flight session later.
 
Output format (one JSON object per line):
    {"ts": 1725900001.234, "topic": "cmd.drone1", "data": {"action": "forward"}}
    {"ts": 1725900001.301, "topic": "state.drone1", "data": {"battery": 87}}
 
BusPlayer reads exactly this format back to replay a session onto a
fresh bus.
"""
 
import json
import time
from pathlib import Path
from typing import Any
 
from core.fileops import get_fileops
from core.bus_player_recorder.recorder_base import RecorderBase
 
 
class BusRecorder(RecorderBase):
    def __init__(self, log_path: str | Path):
        self.log_path = Path(log_path)
        self._fileops = get_fileops()
 
    def attach(self, bus) -> None:
        """Start recording every event published on `bus`."""
        bus.subscribe("*", self._on_event)
 
    def detach(self, bus) -> None:
        """Stop recording events from `bus`. Safe to call even if never attached."""
        bus.unsubscribe("*", self._on_event)
 
    def _on_event(self, topic: str, data: Any) -> None:
        entry = {"ts": time.time(), "topic": topic, "data": data}
        self._fileops.append_line(self.log_path, json.dumps(entry, default=str))