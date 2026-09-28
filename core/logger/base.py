"""
LoggerBase — Interface for logging operations.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from enum import IntEnum
from fnmatch import fnmatchcase


class LogLevel(IntEnum):
    """Enum for log levels."""

    DEBUG = 1
    INFO = 2
    WARNING = 3
    ERROR = 4
    CRITICAL = 5


class LoggerBase(ABC):
    """Each implementation must fulfill this interface."""

    def __init__(self, min_level: LogLevel, exclude_topics: tuple, exclude_data: tuple):
        self.min_level = min_level
        self.exclude_topics = tuple(exclude_topics)
        self.exclude_data = tuple(exclude_data)

    def log_bus_event(self, topic: str, data, level: LogLevel = LogLevel.INFO) -> None:
        """Bus-callback-compatible: bus.subscribe("*", logger.log_bus_event)"""
        if self.is_excluded(topic, data):
            return
        self.log(level, f"{topic}: {data}")

    def log(self, level: LogLevel, message, **context) -> None:
        """Log a message if the level is above the minimum level."""
        if level >= self.min_level:
            message = self.format_message(level, message, **context)
            self._write(message)

    def is_excluded(self, topic: str, data=None) -> bool:
        """True if this bus event should not be logged at all."""
        if any(fnmatchcase(topic, p) for p in self.exclude_topics):
            return True
        if self.exclude_data and isinstance(data, dict):
            label = data.get("action") or data.get("cmd")  # cmd.* events use 'action', ack.* events use 'cmd'
            if isinstance(label, str) and any(fnmatchcase(label, p) for p in self.exclude_data):
                return True
        return False

    @staticmethod
    def _now_iso():
        return datetime.now().isoformat()

    @staticmethod
    def _now_strf():
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    @abstractmethod
    def format_message(self, level: LogLevel, message, **context) -> str:
        """Format the log message with timestamp and context."""
        raise NotImplementedError

    @abstractmethod
    def _write(self, message) -> None:
        """Write the log message to the appropriate destination."""
        raise NotImplementedError
