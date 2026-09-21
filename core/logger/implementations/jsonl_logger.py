"""
JSONLLogger - Logs entries as single-line JSON records.
"""

import json
from datetime import datetime, timezone

from core.fileops import get_fileops
from core.logger.base import LoggerBase, LogLevel


class JSONLLogger(LoggerBase):
    def __init__(self, min_level: LogLevel = LogLevel.INFO, log_path: str | None = None):
        super().__init__(min_level)
        self.file_path = log_path if log_path else None
        self.fops = get_fileops()

    def format_message(self, level: LogLevel, message: str, **context) -> str:
        """Format log entry as a single-line JSON string."""
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level.name,
            "message": message,
            "context": context if context else {},
        }
        return json.dumps(payload, default=str)

    def _write(self, message: str) -> None:
        """Append the JSON line to file, if a path was supplied."""
        if self.file_path:
            # append_line already creates missing parent folders (e.g.
            # logs/debug_logs/), so this works even on a brand new project.
            self.fops.append_line(self.file_path, message)
