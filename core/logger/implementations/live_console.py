"""
LiveConsoleLogger - Sends Logger messages to the console in real-time.
"""

from datetime import datetime

from core.logger.base import LoggerBase, LogLevel


class LiveConsoleLogger(LoggerBase):
    def __init__(self, min_level: LogLevel = LogLevel.INFO):
        super().__init__(min_level)

    def format_message(self, level: LogLevel, message: str, **context) -> str:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        context_str = " ".join(f"{key}={value}" for key, value in context.items()) if context else ""
        return f"{timestamp}: [{level.name}] - {message} {context_str}".strip()

    def _write(self, message: str) -> None:
        print(message)
