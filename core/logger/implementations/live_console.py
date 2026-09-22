"""
LiveConsoleLogger - Sends Logger messages to the console in real-time.
"""

from core.logger.base import LoggerBase, LogLevel


class LiveConsoleLogger(LoggerBase):
    def format_message(self, level: LogLevel, message, **context) -> str:
        timestamp = self._now_strf()
        context_str = " ".join(f"{key}={value}" for key, value in context.items()) if context else ""
        return f"{timestamp}: [{level.name}] - {message} {context_str}".strip()

    def _write(self, message) -> None:
        print(message)
