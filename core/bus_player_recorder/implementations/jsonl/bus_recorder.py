"""
BusRecorder - subscribes to every event published on the EventBus and
appends each one as a single JSON line, so core.bus_player_recorder's
BusPlayer can replay a whole flight session later.

Two things are deliberately NOT recorded verbatim:
  - topics matching `exclude_topics` (default: "video.*") - raw video
    frames don't belong in a JSONL text log.
  - any event whose `data` isn't JSON-safe (see schema.is_json_safe) -
    rather than silently mangling e.g. numpy arrays via
    json.dumps(default=str), those events are silently skipped.

Output format (one JSON object per line) - see schema.BusLogEntry:
    {"ts": 1725900001.234, "topic": "cmd.drone1", "data": {"action": "forward"}}
    {"ts": 1725900001.301, "topic": "state.drone1", "data": {"battery": 87}}

BusPlayer reads exactly this format back to replay a session onto a
fresh bus.
"""

import asyncio
import fnmatch
import time
from pathlib import Path
from typing import Any, Iterable

from core.bus_player_recorder.recorder_base import RecorderBase
from core.bus_player_recorder.schema import BusLogEntry, is_json_safe
from core.fileops import get_fileops

DEFAULT_EXCLUDE_TOPICS = ("frame.*",)


class BusRecorder(RecorderBase):
    def __init__(self, log_path: str | Path, exclude_topics: Iterable[str] = DEFAULT_EXCLUDE_TOPICS):
        self.log_path = Path(log_path)
        self.exclude_topics = tuple(exclude_topics)
        self._fileops = get_fileops()

    def attach(self, bus) -> None:
        """Start recording every event published on `bus`."""
        bus.subscribe("*", self._on_event)

    def detach(self, bus) -> None:
        """Stop recording events from `bus`. Safe to call even if never attached."""
        bus.unsubscribe("*", self._on_event)

    def _is_excluded(self, topic: str) -> bool:
        return any(fnmatch.fnmatch(topic, pattern) for pattern in self.exclude_topics)

    async def _on_event(self, topic: str, data: Any) -> None:
        # The bus awaits every subscriber before publish() returns, so this
        # must never block the event loop - the actual disk write happens
        # in a worker thread.
        if self._is_excluded(topic):
            return

        if not is_json_safe(data):
            # Silently dropped rather than crashing the whole publish() call -
            return

        entry = BusLogEntry(ts=time.time(), topic=topic, data=data)
        await asyncio.to_thread(self._fileops.append_line, self.log_path, entry.to_line())
