"""
LoggerBase — Interface for logging operations.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from enum import IntEnum


class LogLevel(IntEnum):
    """Enum for log levels."""

    DEBUG = 1
    INFO = 2
    WARNING = 3
    ERROR = 4
    CRITICAL = 5


class LoggerBase(ABC):
    """Each implementation must fulfill this interface."""

    def __init__(self, min_level: LogLevel):
        self.min_level = min_level

    def log(self, level: LogLevel, message, **context) -> None:
        """Log a message if the level is above the minimum level."""
        if level >= self.min_level:
            message = self.format_message(level, message, **context)
            self._write(message)

    def _now_iso():
        return datetime.now().isoformat()

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
