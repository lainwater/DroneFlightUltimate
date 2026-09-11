"""
public API of core.logger.
 
The rest of the app always does:
    from core.logger import get_logger, LoggerType
    logger = get_logger(LoggerType.LIVE_CONSOLE)
 
...and never a direct import like
    from core.fileops.implementations.live_console import LiveConsoleLogger
"""
 
from enum import Enum
from .base import LoggerBase, LogLevel

class LoggerType(Enum):
    """Enum for different logger types."""
    LIVE_CONSOLE = "live_console"
    RECORD = "record"
    NOLOGGER = "nologger"

def get_logger(
    loggertype: LoggerType,
    min_level: LogLevel = LogLevel.INFO,
    log_path: str | None = None
    ) -> LoggerBase:
    """Create a new logger instance using the default implementation."""
    match loggertype:
        case LoggerType.LIVE_CONSOLE:
            from .implementations.live_console import LiveConsoleLogger
            return LiveConsoleLogger(min_level=min_level)
        case LoggerType.RECORD:
            from .implementations.jsonl_logger import JSONLLogger
            return JSONLLogger(min_level=min_level, log_path=log_path)
        case LoggerType.NOLOGGER:
            from .implementations.no_logger import NoLogger
            return NoLogger(min_level=min_level)
        case _:
            raise ValueError(f"Unknown logger type: {loggertype}")


__all__ = ["LoggerType", "LogLevel", "LoggerBase", "get_logger"]