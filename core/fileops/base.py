"""
FileOpsBase — Interface for platform-independent file system operations.

Wraps directiory stuff, json read&write, toml read&write and appending lines to a file.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class FileOpsBase(ABC):
    """Each platform implementation must fulfill this interface."""

    @abstractmethod
    def join(self, *parts: str) -> Path:
        """Adds path parts together in a platform-independent way"""
        raise NotImplementedError

    @abstractmethod
    def ensure_dir(self, path: Path) -> Path:
        """Creates the folder (inclusive of all parent folders) if it doenst exist.
        Gives the path back."""
        raise NotImplementedError

    @abstractmethod
    def project_log_dir(self, project_root: Path, subfolder: str) -> Path:
        """Builds <project_root>/logs/<subfolder> ('bus_logs',
        'debug_logs', 'pictures', 'videos') and ensures the folder exists."""
        raise NotImplementedError

    @abstractmethod
    def read_json(self, path: Path) -> dict[str, Any]:
        """Loads a JSON-File as dict."""
        raise NotImplementedError

    @abstractmethod
    def write_json(self, path: Path, data: dict[str, Any]) -> None:
        """Writes a dict as formatted JSON. Creates missing parent folders automatically."""
        raise NotImplementedError
    
    @abstractmethod
    def read_toml(self, path: Path)-> dict[str, Any]:
        """Loads a TOML-File as dict."""
        raise NotImplementedError
    
    @abstractmethod
    def write_toml(self, path: Path, data: dict[str, Any]) -> None:
        """Writes a dict as TOML. Creates missing parent folders automatically."""
        raise NotImplementedError

    @abstractmethod
    def append_line(self, path: Path, line: str) -> None:
        """Adds a single line to a file. Creates the file/parent folders if necessary."""
        raise NotImplementedError

    @abstractmethod
    def platform_name(self) -> str:
        """Short, human-readable name of the current platform."""
        raise NotImplementedError