"""
Keyboard layout files live next to this file:

    keyboard.json        - flying, drone info, project keys
    keyboard_video.json  - everything from keyboard.json + video/stream keys

They don't use Y or Z (the only letters QWERTZ and QWERTY swap), so the same
file works on every keyboard - no layout detection needed.
"""

from pathlib import Path

LAYOUT_DIR = Path(__file__).parent
DEFAULT_LAYOUT = "keyboard"


def available_layouts() -> list[str]:
    return sorted(p.stem for p in LAYOUT_DIR.glob("*.json"))


def layout_path(layout: str | None) -> Path:
    """Layout name (or None = DEFAULT_LAYOUT) -> path of its .json.
    Raises ValueError with the available names if it does not exist."""
    name = layout or DEFAULT_LAYOUT
    path = LAYOUT_DIR / f"{name}.json"
    if not path.exists():
        hint = ""
        if name.lower() in ("qwertz", "qwerty"):
            hint = " The qwertz/qwerty layouts were replaced: use 'keyboard' (no video) or 'keyboard_video'."
        raise ValueError(f"Keyboard layout '{name}' not found. Available: {', '.join(available_layouts())}.{hint}")
    return path
