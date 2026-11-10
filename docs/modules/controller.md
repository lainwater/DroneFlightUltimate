# core.controller

Turns key presses / stick movements into bus commands.

```python
from core.controller import ControllerType, get_controller

controller = get_controller(ControllerType.KEYBOARD, drone_id="drone1", bus=bus, layout="keyboard_video")
await controller.start_controller()
print(controller.controls_text())        # the controls, generated from the layout file
...
await controller.stop_controller()
```

## Keyboard

Two layouts. They work on QWERTZ and QWERTY alike (Y and Z, the swapped letters, are not used):

- `keyboard`: flying, drone info, project keys
- `keyboard_video`: all of `keyboard` + video keys

`layout=None` means `keyboard`. Other names (e.g. the old `qwertz`) raise an error listing the available ones.

| Keys | Action | Keys | Action |
|---|---|---|---|
| W / S | up / down | T / L | takeoff / land |
| A / D | yaw left / right | Space | EMERGENCY (motors off) |
| arrows | forward / back / left / right | C | connect |
| V / B | arm / disarm | I / O | state receiver on / off |
| U / P | get attitude / position | 9 / 0 | misc_1 / misc_2 → `project.<id>` |
| **keyboard_video** | | | |
| J / K | drone video on / off | 1 / 2 | forward / downward camera |
| 3 / 4 | YOLO on / off | 5 / 6 | ArUco on / off |
| 7 / 8 | undistort on / off | N / M | stats overlay on / off |
| F / G | FPV goggles on / off | E / R | record start / stop |
| Q | snapshot | | |

Movement keys send `rc` with ±1 while held and 0 on release. Several keys at once combine.
The keyboard is read **system-wide** (pynput), also when another window is focused. Caps lock doesn't matter.

### Layout file format

`core/controller/implementations/keyboard_controller/<layout>.json`, key = character or pynput key name
(`space`, `up`, `down`, `left`, `right`, `esc`, `tab`, `enter`, ...):

```json
{
  "t": { "on_press": "takeoff", "group": "Flight", "desc": "takeoff" },
  "w": { "rc_axis": "z", "rc_sign": 1, "group": "Flight", "desc": "up" },
  "5": { "on_press": "start_aruco", "target": "stream", "group": "Video", "desc": "ArUco markers on" },
  "9": { "on_press": "misc_1", "target": "project", "group": "Project", "desc": "misc_1 (project)" }
}
```

| Field | |
|---|---|
| `on_press` / `on_release` | action sent as `{"action": ...}` |
| `rc_axis` + `rc_sign` | held-key movement on `x`, `y`, `z` or `yaw` |
| `target` | `drone` (default, `cmd.<id>`), `stream` (`cmd.stream.<id>`, video window), `project` (`project.<id>`) |
| `group`, `desc` | only for `controls_text()` |

Make your own: copy `keyboard_video.json` to `my_layout.json` in the same folder and set `layout = "my_layout"`.
`tests/core/controller/controller_test.py` checks that every action exists, so run `pytest` after editing.

## Joystick (RadioMaster T8L or any pygame gamepad)

Plug it in and turn it on **before** starting. Layouts in `joystick_controller/`:

- `t8l_pos` (default): sticks = rc; SE arm, SA get position, SC land/takeoff, SB disconnect/connect
- `t8l_video`: sticks = rc; SE takeoff/land, SA arm, SC FPV/stats (video), SB drone video/state receiver

```json
{
  "deadzone": 0.15,
  "axes": {
    "0": { "type": "rc", "axis": "x", "invert": false },
    "6": { "type": "switch", "name": "SC", "target": "stream",
           "positions": { "up": "fpv_on", "middle": null, "down": "show_state_on" } }
  }
}
```

Switches fire on change only. The position at start is taken as "current", not as a command.
Two-position switches use `negative` / `positive`, three-position ones `up` / `middle` / `down`.
Find your axis numbers with a pygame joystick test script, or by printing `event.axis` in `_handle_axis`.
