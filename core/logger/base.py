"""
LoggerBase — Interface for logging operations.
"""

from abc import ABC, abstractmethod
from enum import IntEnum


class LogLevel(IntEnum):
    """Enum for log levels."""

    DEBUG = 1
    INFO = 2
    WARNING = 3
    ERROR = 4


class LoggerBase(ABC):
    """Each implementation must fulfill this interface."""

    def __init__(self, min_level: LogLevel):
        self.min_level = min_level

    def log(self, level: LogLevel, message: str, **context) -> None:
        """Log a message if the level is above the minimum level."""
        if level >= self.min_level:
            message = self.format_message(level, message, **context)
            self._write(message)

    @abstractmethod
    def format_message(self, level: LogLevel, message: str, **context) -> str:
        """Format the log message with timestamp and context."""
        raise NotImplementedError

    @abstractmethod
    def _write(self, message) -> None:
        """Write the log message to the appropriate destination."""
        raise NotImplementedError
