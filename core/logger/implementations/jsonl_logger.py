"""
JSONLLogger - Logs entries as single-line JSON records.
"""

import json

from core.fileops import errors, get_fileops
from core.logger.base import LoggerBase, LogLevel


class JSONLLogger(LoggerBase):
    def __init__(self, min_level: LogLevel = LogLevel.INFO, exclude_data: tuple = (), exclude_topics: tuple = (), log_path: str | None = None):
        super().__init__(min_level, exclude_data, exclude_topics)
        self.file_path = log_path if log_path else None
        self.fops = get_fileops()

    def format_message(self, level: LogLevel, message, **context) -> str:
        """Format log entry as a single-line JSON string."""
        payload = {
            "timestamp": self._now_iso(),
            "level": level.name,
            "message": message,
            "context": context if context else {},
        }
        return json.dumps(payload, default=str)

    def _write(self, message) -> None:
        """Append the JSON line to file, if a path was supplied."""
        if self.file_path:
            # append_line already creates missing parent folders (e.g.
            # logs/debug_logs/), so this works even on a brand new project.
            try:
                self.fops.append_line(self.file_path, message)
            except errors.FileOpsWriteError as e:
                raise e
