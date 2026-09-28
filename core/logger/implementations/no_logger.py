"""
NoLogger - Silently suppresses all logging operations.
"""

from core.logger.base import LoggerBase, LogLevel


class NoLogger(LoggerBase):
    def __init__(self, min_level: LogLevel = LogLevel.INFO, exclude_topics: tuple = (), exclude_data: tuple = ()):
        super().__init__(min_level, exclude_topics, exclude_data)

    def log_bus_event(self, topic: str, data, level: LogLevel = LogLevel.INFO) -> None:
        """Short-circuit log execution to avoid formatting overhead."""
        pass

    def log(self, level: LogLevel, message, **context) -> None:
        """Short-circuit log execution to avoid formatting overhead."""
        pass

    def format_message(self, level: LogLevel, message, **context) -> str:
        return ""

    def _write(self, message) -> None:
        pass
