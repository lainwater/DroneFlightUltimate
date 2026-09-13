"""
WinFileOps — Windows-Implementation of FileOpsBase.
"""

import json
import platform
from pathlib import Path
from typing import Any
import toml

from core.fileops.base import FileOpsBase


class WinFileOps(FileOpsBase):
    def join(self, *parts: str) -> Path:
        return Path(*parts)

    def ensure_dir(self, path: Path) -> Path:
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def project_log_dir(self, project_root: Path, subfolder: str) -> Path:
        log_dir = Path(project_root) / "logs" / subfolder
        return self.ensure_dir(log_dir)

    def read_json(self, path: Path) -> dict[str, Any]:
        path = Path(path)
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def write_json(self, path: Path, data: dict[str, Any]) -> None:
        path = Path(path)
        self.ensure_dir(path.parent)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def read_toml(self, path: Path)-> dict[str, Any]:
        path = Path(path)
        with open(path, "r", encoding="utf-8") as f:
                return toml.load(f)
            
    def write_toml(self, path: Path, data: dict[str, Any]) -> None:
            path = Path(path)
            self.ensure_dir(path.parent)
            with open(path, "w", encoding="utf-8") as f:
                toml.dump(data, f)

    def append_line(self, path: Path, line: str) -> None:
        path = Path(path)
        self.ensure_dir(path.parent)
        with open(path, "a", encoding="utf-8") as f:
            f.write(line.rstrip("\n") + "\n")

    def platform_name(self) -> str:
        return f"windows-{platform.machine()}"