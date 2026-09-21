"""
BusPlayer - replays a previously recorded JSON-Lines bus session back
onto an EventBus, preserving the original relative timing between
events (scaled by `speed`).

Reads exactly the format written by BusRecorder:
    {"ts": 1725900001.234, "topic": "cmd.drone1", "data": {"action": "forward"}}
"""

import asyncio
import json
import time
from pathlib import Path
from typing import Any

from core.bus_player_recorder.player_base import PlayerBase


class BusPlayer(PlayerBase):
    def __init__(self, log_path: str | Path):
        self.log_path = Path(log_path)

    def _load_entries(self) -> list[dict[str, Any]]:
        with open(self.log_path, "r", encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]

    async def play(self, bus, speed: float = 1.0) -> None:
        entries = self._load_entries()
        if not entries:
            return

        t0 = entries[0]["ts"]
        start = time.monotonic()

        for entry in entries:
            elapsed_original = (entry["ts"] - t0) / speed
            elapsed_real = time.monotonic() - start
            wait = elapsed_original - elapsed_real
            if wait > 0:
                await asyncio.sleep(wait)
            await bus.publish(entry["topic"], entry["data"])
