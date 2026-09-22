"""
NoLogger - Silently suppresses all logging operations.
"""

from core.logger.base import LoggerBase, LogLevel


class NoLogger(LoggerBase):
    def __init__(self, min_level: LogLevel = LogLevel.INFO):
        super().__init__(min_level)

    def log(self, level: LogLevel, message, **context) -> None:
        """Short-circuit log execution to avoid formatting overhead."""
        pass

    def format_message(self, level: LogLevel, message, **context) -> str:
        return ""

    def _write(self, message) -> None:
        pass
