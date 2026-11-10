# more_examples

Bigger, task-style projects. They build on the basics in `projects/examples/`.
Run them with `-m`:

```bash
python run.py run -m                       # list
python run.py run -m -n tello_patterns
```

The name prefix tells you which drone is needed:

| Prefix | Needs |
|---|---|
| `sim_` | nothing (simdrone, laptop camera) |
| `tello_` | **any Tello**: basic Tello, Tello EDU or Tello Talent (and mostly the simdrone too) |
| `edu_` | **Tello EDU or Tello Talent**: mission pads and/or station mode (own Wi-Fi network) |
| `talent_` | **Tello Talent** (RoboMaster TT) with the expansion kit: LED, dot matrix, ToF sensor |
| `vicon_` | Tello EDU / Talent on the Vicon lab network + `vicon_dssdk` |

| Project | What it shows |
|---|---|
| `sim_yolo` | everything auto-started (telemetry, video, stats overlay, YOLO) |
| `tello_patterns` | key 9 flies the next pattern of `core.patterns` (square, triangle, hexagon, circle, waypoints, orbit, dance, ...), key 0 stops |
| `tello_command_test` | steps through all commands; skips what your `model` can't do |
| `fly_to_marker` | key 9: turn to an ArUco marker and hold 1 m in front of it (closed loop) |
| `edu_pad_pose_orbit` | localization from mission pads in a standard right-handed world frame, orbit on key 9, dance over pad 6, lands when YOLO sees a phone |
| `edu_search_and_rescue` | lawnmower search, lands on the target mission pad, manual keys take over |
| `edu_multi_tello` | several Tellos: mirrored keyboard flight, all fly a pattern on key 9 (setup steps inside) |
| `talent_cooling_battery_gauge` | motors on when the board gets hot, battery gauge on the dot matrix |
| `talent_tof_ruler` | ToF distance scrolled over the dot matrix |
| `vicon_yolo` | keyboard flight, YOLO and the Vicon pose on the video |
| `vicon_position_control` | key 9 flies to / holds waypoints using Vicon (closed loop) |

Set the drone's `model` in `config/mydrone.json` (`tello`, `tello_edu`, `tello_talent`). Then a
command your drone can't do answers `error NotSupported` instead of being sent.

Helper files next to `main.py` (e.g. `commander/control.py`) are imported by name: `from control import ...`.
The pure ones are tested in `tests/more_examples/`.

Copy a project to `projects/` to change it: `projects/*` is not tracked by git; `more_examples/` is.
