"""
BusLogEntry - the single source of truth for the on-disk record shape
shared by every Recorder/Player implementation:

    {"ts": 1725900001.234, "topic": "cmd.drone1", "data": {"action": "forward"}}

Both BusRecorder and BusPlayer import this instead of hand-rolling
dict literals / json.dumps calls, so the schema can't drift between
the write side and the read side.
"""

import json
from dataclasses import dataclass
from typing import Any


class BusLogEntryError(ValueError):
    """Raised when a line can't be parsed into a BusLogEntry (corrupt
    JSON, or missing 'ts'/'topic'/'data' keys)."""


@dataclass(frozen=True, slots=True)
class BusLogEntry:
    ts: float
    topic: str
    data: Any

    def to_line(self) -> str:
        """Serialize to a single JSON line (no trailing newline)."""
        return json.dumps({"ts": self.ts, "topic": self.topic, "data": self.data}, ensure_ascii=False)

    @classmethod
    def from_line(cls, line: str) -> "BusLogEntry":
        """Parse a single JSON line. Raises BusLogEntryError on anything
        that isn't a well-formed record, so callers can decide whether
        to skip-and-warn (BusPlayer) or fail hard."""
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as e:
            raise BusLogEntryError(f"invalid JSON: {e}") from e

        if not isinstance(obj, dict):
            raise BusLogEntryError(f"expected a JSON object, got {type(obj).__name__}")

        try:
            return cls(ts=obj["ts"], topic=obj["topic"], data=obj["data"])
        except KeyError as e:
            raise BusLogEntryError(f"missing required key {e}") from e


def is_json_safe(value: Any) -> bool:
    """Whitelist check for values allowed as bus-log `data` payloads:
    only plain JSON-representable types, recursively. Anything else
    (bytes, numpy arrays, custom objects, video frames, ...) is
    rejected rather than silently mangled by json.dumps(default=str).
    """
    if value is None or isinstance(value, (str, int, float, bool)):
        return True
    if isinstance(value, dict):
        return all(isinstance(k, str) and is_json_safe(v) for k, v in value.items())
    if isinstance(value, (list, tuple)):
        return all(is_json_safe(v) for v in value)
    return False
