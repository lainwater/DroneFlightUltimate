"""
BusPlayer - replays a previously recorded JSON-Lines bus session back
onto an EventBus, preserving the original relative timing between
events (scaled by `speed`), with pause/resume and single-step support.

Reads exactly the format written by BusRecorder - see schema.BusLogEntry:
    {"ts": 1725900001.234, "topic": "cmd.drone1", "data": {"action": "forward"}}

The file is read lazily, one line at a time, instead of being loaded
into memory upfront: playback can start immediately and memory usage
stays constant regardless of log size. Malformed lines (e.g. a log cut
off mid-write after a crash) are silently skipped rather than aborting
playback - replaying a crashed flight for debugging is one of the main
reasons to use this at all.
"""

import asyncio
import time
from pathlib import Path
from typing import Iterator

from core.bus_player_recorder.player_base import PlayerBase
from core.bus_player_recorder.schema import BusLogEntry, BusLogEntryError

# How often play() wakes up while waiting for the next event's
# scheduled time, so a pause() takes effect promptly instead of only
# being noticed after a possibly-long sleep.
_POLL_INTERVAL_S = 0.1


class BusPlayer(PlayerBase):
    def __init__(self, log_path: str | Path):
        self.log_path = Path(log_path)
        self._entries: Iterator[BusLogEntry] | None = None
        self._paused = asyncio.Event()
        self._paused.set()  # not paused by default

    def _iter_entries(self) -> Iterator[BusLogEntry]:
        with open(self.log_path, "r", encoding="utf-8") as f:
            for lineno, raw_line in enumerate(f, start=1):
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    yield BusLogEntry.from_line(line)
                except BusLogEntryError:
                    # Corrupt/truncated line (e.g. a crash mid-write) - skip
                    # it and keep playing rather than aborting the whole
                    # replay.
                    continue

    def _ensure_entries(self) -> Iterator[BusLogEntry]:
        if self._entries is None:
            self._entries = self._iter_entries()
        return self._entries

    def pause(self) -> None:
        self._paused.clear()

    def resume(self) -> None:
        self._paused.set()

    async def step(self, bus) -> bool:
        entry = next(self._ensure_entries(), None)
        if entry is None:
            return False
        await bus.publish(entry.topic, entry.data)
        return True

    async def play(self, bus, speed: float = 1.0) -> None:
        entries = self._ensure_entries()
        first = next(entries, None)
        if first is None:
            return

        t0 = first.ts
        start = time.monotonic()
        paused_total = 0.0

        async def wait_until_due(entry: BusLogEntry) -> None:
            nonlocal paused_total
            elapsed_original = (entry.ts - t0) / speed
            while True:
                if not self._paused.is_set():
                    pause_start = time.monotonic()
                    await self._paused.wait()
                    paused_total += time.monotonic() - pause_start

                elapsed_real = time.monotonic() - start - paused_total
                wait = elapsed_original - elapsed_real
                if wait <= 0:
                    return
                # Sleep in short slices so a pause() during a long wait is
                # noticed quickly instead of only after the full sleep.
                await asyncio.sleep(min(wait, _POLL_INTERVAL_S))

        await wait_until_due(first)
        await bus.publish(first.topic, first.data)

        for entry in entries:
            await wait_until_due(entry)
            await bus.publish(entry.topic, entry.data)
