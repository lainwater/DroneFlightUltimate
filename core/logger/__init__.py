"""
public API of core.logger.

The rest of the app always does:
    from core.logger import get_logger, LoggerType
    logger = get_logger(LoggerType.LIVE_CONSOLE)
    self.bus.subscribe("*", self.live_logger.log_bus_event)

...and never a direct import like
    from core.logger.implementations.live_console import LiveConsoleLogger
"""

from enum import Enum

from .base import LoggerBase, LogLevel


class LoggerType(Enum):
    """Enum for different logger types."""

    LIVE_CONSOLE = "live_console"
    JSONL = "jsonl"
    NOLOGGER = "nologger"


DEFAULT_EXCLUDE_TOPICS = ("frame.*",)
DEFAULT_EXCLUDE_DATA = ("rc", "rc *")


def get_logger(
    loggertype: LoggerType,
    min_level: LogLevel = LogLevel.INFO,
    log_path: str | None = None,
    exclude_topics: tuple = DEFAULT_EXCLUDE_TOPICS,
    exclude_data: tuple = DEFAULT_EXCLUDE_DATA,
) -> LoggerBase:
    """Create a new logger instance using the default implementation."""
    match loggertype:
        case LoggerType.LIVE_CONSOLE:
            from .implementations.live_console import LiveConsoleLogger

            return LiveConsoleLogger(min_level=min_level, exclude_topics=exclude_topics, exclude_data=exclude_data)
        case LoggerType.JSONL:
            from .implementations.jsonl_logger import JSONLLogger

            return JSONLLogger(min_level=min_level, log_path=log_path, exclude_topics=exclude_topics, exclude_data=exclude_data)
        case LoggerType.NOLOGGER:
            from .implementations.no_logger import NoLogger

            return NoLogger(min_level=min_level)


__all__ = ["LoggerType", "LogLevel", "LoggerBase", "get_logger"]
