"""
Tests for core.logger.

Run with: pytest tests/core/logger/logger_test.py -v
"""

import io
import json
from contextlib import redirect_stdout

from core.logger import LoggerType, LogLevel, get_logger
from core.logger.implementations.jsonl_logger import JSONLLogger
from core.logger.implementations.live_console import LiveConsoleLogger
from core.logger.implementations.no_logger import NoLogger

# ---------------------------------------------------------------------
# get_logger factory
# ---------------------------------------------------------------------


def test_get_logger_returns_correct_type_for_each_enum_value():
    assert isinstance(get_logger(LoggerType.LIVE_CONSOLE), LiveConsoleLogger)
    assert isinstance(get_logger(LoggerType.NOLOGGER), NoLogger)
    assert isinstance(get_logger(LoggerType.RECORD, log_path="unused.jsonl"), JSONLLogger)


# ---------------------------------------------------------------------
# LiveConsoleLogger
# ---------------------------------------------------------------------


def test_live_console_logger_prints_message_and_context():
    logger = get_logger(LoggerType.LIVE_CONSOLE, min_level=LogLevel.INFO)
    buf = io.StringIO()

    with redirect_stdout(buf):
        logger.log(LogLevel.INFO, "Connected to drone", drone_id="drone1")

    output = buf.getvalue()
    assert "[INFO]" in output
    assert "Connected to drone" in output
    assert "drone_id=drone1" in output


def test_live_console_logger_filters_below_min_level():
    logger = get_logger(LoggerType.LIVE_CONSOLE, min_level=LogLevel.WARNING)
    buf = io.StringIO()

    with redirect_stdout(buf):
        logger.log(LogLevel.DEBUG, "Ack timeout, retrying")

    assert buf.getvalue() == ""


def test_live_console_logger_allows_message_at_exactly_min_level():
    logger = get_logger(LoggerType.LIVE_CONSOLE, min_level=LogLevel.WARNING)
    buf = io.StringIO()

    with redirect_stdout(buf):
        logger.log(LogLevel.WARNING, "Low battery")

    assert "Low battery" in buf.getvalue()


# ---------------------------------------------------------------------
# JSONLLogger
# ---------------------------------------------------------------------


def test_jsonl_logger_writes_valid_json_lines(tmp_path):
    path = tmp_path / "debug_logs" / "session.jsonl"
    logger = get_logger(LoggerType.RECORD, min_level=LogLevel.DEBUG, log_path=str(path))

    logger.log(LogLevel.INFO, "Connected", drone_id="drone1")
    logger.log(LogLevel.ERROR, "Connection lost")

    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2

    first = json.loads(lines[0])
    assert first["level"] == "INFO"
    assert first["message"] == "Connected"
    assert first["context"] == {"drone_id": "drone1"}

    second = json.loads(lines[1])
    assert second["level"] == "ERROR"
    assert second["context"] == {}


def test_jsonl_logger_creates_missing_parent_dirs(tmp_path):
    # Parent folder does not exist yet, unlike a fresh project checkout.
    path = tmp_path / "logs" / "debug_logs" / "session.jsonl"
    logger = get_logger(LoggerType.RECORD, log_path=str(path))

    logger.log(LogLevel.INFO, "hello")

    assert path.exists()


def test_jsonl_logger_without_path_does_not_raise():
    logger = JSONLLogger(min_level=LogLevel.DEBUG, log_path=None)
    logger.log(LogLevel.INFO, "no path given, should just no-op")


def test_jsonl_logger_respects_min_level(tmp_path):
    path = tmp_path / "session.jsonl"
    logger = get_logger(LoggerType.RECORD, min_level=LogLevel.ERROR, log_path=str(path))

    logger.log(LogLevel.INFO, "should be filtered out")

    assert not path.exists()


# ---------------------------------------------------------------------
# NoLogger
# ---------------------------------------------------------------------


def test_no_logger_writes_nothing_to_stdout():
    logger = get_logger(LoggerType.NOLOGGER, min_level=LogLevel.DEBUG)
    buf = io.StringIO()

    with redirect_stdout(buf):
        logger.log(LogLevel.ERROR, "this should never appear")

    assert buf.getvalue() == ""
