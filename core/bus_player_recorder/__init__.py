"""
Public API of core.bus_player_recorder.

    from core.bus_player_recorder import get_recorder, get_player

Recorder and Player live in the same package on purpose: they share
the same on-disk JSONL schema ({"ts", "topic", "data"}), even though
at runtime they're used at completely different times (Recorder during
a live flight, Player afterwards for replay/debugging).
"""

from pathlib import Path

from .player_base import PlayerBase
from .recorder_base import RecorderBase


def get_recorder(log_path: str | Path) -> RecorderBase:
    """Create a JSONL bus recorder writing to `log_path`."""
    from .implementations.jsonl.bus_recorder import BusRecorder

    return BusRecorder(log_path)


def get_player(log_path: str | Path) -> PlayerBase:
    """Create a JSONL bus player reading from `log_path`."""
    from .implementations.jsonl.bus_player import BusPlayer

    return BusPlayer(log_path)


__all__ = ["PlayerBase", "RecorderBase", "get_recorder", "get_player"]
