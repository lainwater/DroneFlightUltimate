"""
Public API of core.bus_player_recorder.

    from core.bus_player_recorder import get_recorder, get_player

Recorder and Player live in the same package on purpose: they share
the same on-disk record shape (schema.BusLogEntry), even though at
runtime they're used at completely different times (Recorder during
a live flight, Player afterwards for replay/debugging).
"""

from pathlib import Path

from .player_base import PlayerBase
from .recorder_base import RecorderBase

_RECORDER_FORMATS = {
    "jsonl": ("core.bus_player_recorder.implementations.jsonl.bus_recorder", "BusRecorder"),
}
_PLAYER_FORMATS = {
    "jsonl": ("core.bus_player_recorder.implementations.jsonl.bus_player", "BusPlayer"),
}


def get_recorder(log_path: str | Path, format: str = "jsonl") -> RecorderBase:
    """Create a bus recorder writing to `log_path` in the given `format`."""
    return _instantiate(_RECORDER_FORMATS, format, log_path)


def get_player(log_path: str | Path, format: str = "jsonl") -> PlayerBase:
    """Create a bus player reading from `log_path` in the given `format`."""
    return _instantiate(_PLAYER_FORMATS, format, log_path)


def _instantiate(registry: dict, format: str, log_path: str | Path):
    if format not in registry:
        raise ValueError(f"Unknown bus_player_recorder format '{format}'. Available: {sorted(registry)}")
    import importlib

    module_name, class_name = registry[format]
    module = importlib.import_module(module_name)
    return getattr(module, class_name)(log_path)


__all__ = ["PlayerBase", "RecorderBase", "get_recorder", "get_player"]
