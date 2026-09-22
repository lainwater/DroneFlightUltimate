"""
Exception hierarchy for core.fileops.

Every FileOps backend must raise these instead of leaking raw stdlib
exceptions (OSError, json.JSONDecodeError, tomllib.TOMLDecodeError, ...),
so the rest of the app only ever needs to catch `FileOpsError`. The
original exception is always chained via `raise ... from e`, so nothing
is lost for debugging.
"""


class FileOpsError(Exception):
    """Base class for all core.fileops errors."""


class FileOpsReadError(FileOpsError):
    """Raised when a file could not be read or parsed (missing file,
    invalid JSON/TOML, permission denied, ...)."""


class FileOpsWriteError(FileOpsError):
    """Raised when a file could not be written (permission denied, disk
    full, invalid parent path, ...)."""


class FileOpsValidationError(FileOpsError):
    """Raised when the caller passed data that FileOps refuses to write
    as-is, e.g. a line for append_line() that contains embedded
    newlines and would corrupt the one-line-per-record format."""
