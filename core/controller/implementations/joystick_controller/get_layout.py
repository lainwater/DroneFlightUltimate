"""
get_layout.py - resolves which joystick JSON profile to load.

Unlike the keyboard controller, there's no reliable way to auto-detect
"which mapping matches this device": pygame can report the joystick's
name (joystick.get_name()), but matching that against a list of known
devices is brittle, and the joystick isn't even connected/initialized
yet at config-load time (that happens later, in start_controller()).
So this stays simple: an explicit `layout` name always wins, and if
none is given, it falls back to "t8l" as the default profile.
"""

from pathlib import Path


def current_joystick_layout_as_json_path(_layout: str | None) -> Path:
    name = _layout or "t8l"
    return Path(__file__).parent / f"{name}.json"