"""
FileOpsBase - platform-independent file system operations.

Wraps directiory stuff, json read&write, toml read&write and appending lines to a file.

Almost none of this is actually platform-specific (pathlib/json/tomllib
behave the same everywhere Python runs), so the concrete logic lives
here as regular methods. Platform subclasses only implement
`platform_name()` - the one thing that genuinely differs per OS. See
core/fileops/implementations/{windows,linux,darwin}.py and
implementations/common.py for the tiny per-OS pieces.

All methods raise `core.fileops.errors.FileOpsError` subclasses on
failure instead of leaking raw OSError/json/tomllib exceptions - the
rest of the app only needs to know about FileOpsError.
"""

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import toml

from core.fileops.errors import FileOpsReadError, FileOpsValidationError, FileOpsWriteError


class FileOpsBase(ABC):
    """Only `platform_name()` must be implemented per platform."""

    def join(self, *parts: str) -> Path:
        """Adds path parts together in a platform-independent way"""
        return Path(*parts)

    def ensure_dir(self, path: Path) -> Path:
        """Creates the folder (inclusive of all parent folders) if it doesn't
        exist. Gives the path back."""
        path = Path(path)
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise FileOpsWriteError(f"Could not create directory '{path}': {e}") from e
        return path

    def project_log_dir(self, project_root: Path, subfolder: str) -> Path:
        """Builds <project_root>/logs/<subfolder> ('bus_logs',
        'debug_logs', 'pictures', 'videos') and ensures the folder exists."""
        log_dir = Path(project_root) / "logs" / subfolder
        return self.ensure_dir(log_dir)

    def read_json(self, path: Path) -> dict[str, Any]:
        """Loads a JSON-File as dict."""
        path = Path(path)
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError as e:
            raise FileOpsReadError(f"JSON file not found: '{path}'") from e
        except json.JSONDecodeError as e:
            raise FileOpsReadError(f"Invalid JSON in '{path}': {e}") from e
        except OSError as e:
            raise FileOpsReadError(f"Could not read JSON file '{path}': {e}") from e

    def write_json(self, path: Path, data: dict[str, Any]) -> None:
        """Writes a dict as formatted JSON. Creates missing parent folders automatically."""
        path = Path(path)
        self.ensure_dir(path.parent)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except (OSError, TypeError) as e:
            raise FileOpsWriteError(f"Could not write JSON file '{path}': {e}") from e

    def read_toml(self, path: Path) -> dict[str, Any]:
        """Loads a TOML-File as dict."""
        path = Path(path)
        try:
            with open(path, "r", encoding="utf-8") as f:
                return toml.load(f)
        except FileNotFoundError as e:
            raise FileOpsReadError(f"TOML file not found: '{path}'") from e
        except toml.TomlDecodeError as e:
            raise FileOpsReadError(f"Invalid TOML in '{path}': {e}") from e
        except OSError as e:
            raise FileOpsReadError(f"Could not read TOML file '{path}': {e}") from e

    def write_toml(self, path: Path, data: dict[str, Any]) -> None:
        """Writes a dict as TOML. Creates missing parent folders automatically."""
        path = Path(path)
        self.ensure_dir(path.parent)
        try:
            with open(path, "w", encoding="utf-8") as f:
                toml.dump(data, f)
        except (OSError, TypeError) as e:
            raise FileOpsWriteError(f"Could not write TOML file '{path}': {e}") from e

    def append_line(self, path: Path, line: str) -> None:
        """Adds a single line to a file. Creates the file/parent folders if necessary.

        `line` must not contain embedded newlines - this file is used for
        JSONL-style logs (one record per line) elsewhere in the app, and a
        stray '\\n' inside `line` would silently split one record into two
        and corrupt every downstream reader (e.g. BusPlayer).
        """
        if "\n" in line or "\r" in line:
            raise FileOpsValidationError(
                "append_line() received a line containing an embedded newline - "
                "this would corrupt the one-line-per-record file format. "
                f"Offending line (repr): {line!r}"
            )

        path = Path(path)
        self.ensure_dir(path.parent)
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError as e:
            raise FileOpsWriteError(f"Could not append to file '{path}': {e}") from e

    @abstractmethod
    def platform_name(self) -> str:
        """Short, human-readable name of the current platform."""
        raise NotImplementedError
