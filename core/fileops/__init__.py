"""
public API of core.fileops.

The rest of the app always does:
    from core.fileops import get_fileops
    fops = get_fileops()

Important:  This is a singelton.
            Unlike other modules it is a global instance and you can just get one Fops.
"""

import platform

from .base import FileOpsBase

_instance: FileOpsBase | None = None

_PLATFORM_CLASSES = {
    "Windows": ("core.fileops.implementations.windows", "WindowsFileOps"),
    "Linux": ("core.fileops.implementations.linux", "LinuxFileOps"),
    "Darwin": ("core.fileops.implementations.darwin", "DarwinFileOps"),
}


def get_fileops() -> FileOpsBase:
    """Returns a (cached) FileOps instance suitable for the current platform."""
    global _instance
    if _instance is not None:
        return _instance

    system = platform.system()
    if system not in _PLATFORM_CLASSES:
        raise NotImplementedError(
            f"No FileOps backend for platform '{system}' implemented. "
            f"Add core/fileops/implementations/{system.lower()}.py (subclassing "
            f"FileOpsBase, implementing only platform_name()) and register it "
            f"in core/fileops/__init__.py's _PLATFORM_CLASSES."
        )

    module_name, class_name = _PLATFORM_CLASSES[system]
    import importlib

    module = importlib.import_module(module_name)
    _instance = getattr(module, class_name)()
    return _instance


__all__ = ["FileOpsBase", "get_fileops"]
