"""
public API of core.fileops.

The rest of the app always does:
    from core.fileops import get_fileops
    fops = get_fileops()
"""

import platform

from .base import FileOpsBase

_instance: FileOpsBase | None = None


def get_fileops() -> FileOpsBase:
    """Returns a (cached) FileOps instance suitable for the current platform."""
    global _instance
    if _instance is not None:
        return _instance

    system = platform.system()
    if system == "Windows":
        from .implementations.win_64x82 import WinFileOps

        _instance = WinFileOps()
    else:
        raise NotImplementedError(
            f"No FileOps-Backend for platform '{system}' implemented. "
            f"Add core/fileops/implementations/{system}.py. And implement it into core/fileops/__init__.py."
        )
    return _instance


__all__ = ["FileOpsBase", "get_fileops"]
