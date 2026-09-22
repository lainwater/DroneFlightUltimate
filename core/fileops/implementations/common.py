"""
Shared helper for the platform_name() piece of FileOpsBase - the one
method that genuinely differs per OS. Each OS-specific FileOps class
is otherwise a one-liner; see windows.py / linux.py / darwin.py.
"""

import platform


def system_platform_name() -> str:
    """e.g. 'windows-amd64', 'linux-x86_64', 'darwin-arm64'."""
    return f"{platform.system().lower()}-{platform.machine().lower()}"
