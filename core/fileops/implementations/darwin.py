"""DarwinFileOps - macOS-Implementation of FileOpsBase.

Everything except platform_name() is platform-independent and lives
in FileOpsBase.
"""

from core.fileops.base import FileOpsBase
from core.fileops.implementations.common import system_platform_name


class DarwinFileOps(FileOpsBase):
    def platform_name(self) -> str:
        return system_platform_name()
