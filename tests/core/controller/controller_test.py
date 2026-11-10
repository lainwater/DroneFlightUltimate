"""Keyboard/joystick layouts: every key must map to an action that exists."""

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
KB = ROOT / "core/controller/implementations/keyboard_controller"
JOY = ROOT / "core/controller/implementations/joystick_controller"
DRONE_ACTIONS = set(json.loads((ROOT / "core/drone/implementations/DJI/tello/commands.json").read_text()))
STREAM_ACTIONS = set(json.loads((ROOT / "core/video/implementations/cv2/commands.json").read_text()))


@pytest.mark.parametrize("layout", ["keyboard", "keyboard_video"])
def test_keyboard_layout_actions_exist(layout):
    config = json.loads((KB / f"{layout}.json").read_text())
    for key, entry in config.items():
        target = entry.get("target", "drone")
        if "on_press" in entry:
            action = entry["on_press"]
            if target == "drone":
                assert action in DRONE_ACTIONS, f"{layout}: {key} -> unknown drone action {action}"
            elif target == "stream":
                assert action in STREAM_ACTIONS, f"{layout}: {key} -> unknown stream action {action}"
            else:
                assert target == "project"
        else:
            assert entry["rc_axis"] in ("x", "y", "z", "yaw") and entry["rc_sign"] in (1, -1)
        assert entry.get("desc"), f"{layout}: {key} has no desc (shown in controls_text)"


@pytest.mark.parametrize("layout", ["keyboard", "keyboard_video"])
def test_keyboard_layout_works_on_qwertz_and_qwerty(layout):
    config = json.loads((KB / f"{layout}.json").read_text())
    assert not {"y", "z"} & set(config), "Y and Z are swapped between QWERTZ and QWERTY"


def test_video_layout_contains_flying_layout():
    base = json.loads((KB / "keyboard.json").read_text())
    video = json.loads((KB / "keyboard_video.json").read_text())
    assert all(video[k] == v for k, v in base.items())


def test_unknown_keyboard_layout_names_alternatives():
    from core.controller.implementations.keyboard_controller.get_layout import layout_path

    assert layout_path(None).name == "keyboard.json"
    with pytest.raises(ValueError, match="keyboard_video"):
        layout_path("qwertz")


@pytest.mark.parametrize("path", sorted(JOY.glob("*.json")), ids=lambda p: p.stem)
def test_joystick_layout_actions_exist(path):
    config = json.loads(path.read_text())
    for axis in config["axes"].values():
        if axis["type"] != "switch":
            continue
        allowed = STREAM_ACTIONS if axis.get("target") == "stream" else DRONE_ACTIONS
        for action in axis["positions"].values():
            assert action is None or action in allowed, f"{path.stem}: {axis['name']} -> unknown action {action}"
