# Examples

```bash
python run.py run -e                     # list
python run.py run -e -n <name>
```

Every example has the same structure (`setup` → `main` → `end_run`) and a docstring at the top of its
`commander/main.py`: what you need, how to run it, what it shows. The controls are printed at start.

## Basics: `<drone>_<controller>[_video]`

| Example | Drone | Controller | Video | Needs |
|---|---|---|---|---|
| `simdrone_keyboard` | simdrone | keyboard | | nothing |
| `simdrone_keyboard_video` | simdrone | keyboard_video | laptop camera | a laptop camera |
| `simdrone_t8l` | simdrone | T8L (`t8l_pos`) | | RadioMaster T8L |
| `simdrone_t8l_video` | simdrone | T8L (`t8l_video`) | laptop camera | T8L + camera |
| `tello_keyboard` | Tello | keyboard | | Tello |
| `tello_keyboard_video` | Tello | keyboard_video | Tello camera | Tello |
| `tello_t8l` | Tello | T8L (`t8l_pos`) | | Tello + T8L |
| `tello_t8l_video` | Tello | T8L (`t8l_video`) | Tello camera | Tello + T8L |

Start here: `simdrone_keyboard`, then `tello_keyboard_video`.

## Features: `feature_<what>`

One feature each, keyboard_video layout. The drone is set in `config/mydrone.json`. Most also work with the
simdrone: set `"drone_type": "sim_simdrone"` and, for calibration, `calibration = "webcam"`.

| Example | Shows | Default drone |
|---|---|---|
| `feature_project_commands` | keys 9/0 → `project.<id>` → your code asks the drone for its battery → shown on the video. The pattern for your own keys. | simdrone |
| `feature_aruco` | undistort + ArUco on at start; closest marker's x/y/z/distance/angles drawn top-right; results via `data.stream.<id>` | Tello |
| `feature_yolo` | YOLO on at start; object count per label top-right | Tello |
| `feature_vicon` | Vicon pose of the Tello top-right; `[vicon]` in defaults.toml | Tello at `192.168.10.133` |

## more_examples/: bigger, task-style projects

`python run.py run -m -n <name>`. The prefix says which drone is needed:
`sim_` none, `tello_` any Tello, `edu_` Tello EDU or Talent, `talent_` Talent with expansion kit, `vicon_` the Vicon lab.

| Project | Shows |
|---|---|
| `sim_yolo` | everything auto-started (telemetry, video, stats overlay, YOLO) |
| `tello_patterns` | key 9 = next flight pattern (square, triangle, hexagon, circle, waypoints, orbit, dance, ...), 0 = stop |
| `tello_command_test` | steps through all commands, skips what your `model` can't do |
| `fly_to_marker` | closed loop: turn to an ArUco marker and hold 1 m in front of it |
| `edu_pad_pose_orbit` | localization from mission pads (standard right-handed world frame), orbit, dance over a pad, lands when YOLO sees a phone |
| `edu_search_and_rescue` | lawnmower search, interrupts and lands on the target mission pad, manual keys take over |
| `edu_multi_tello` | several Tellos: one keyboard flies all, all fly a pattern at once (setup steps inside) |
| `talent_cooling_battery_gauge` | motor-on cooling when hot, battery gauge on the dot matrix |
| `talent_tof_ruler` | ToF distance on the dot matrix |
| `vicon_yolo` | keyboard flight, YOLO and the Vicon pose on the video |
| `vicon_position_control` | closed loop: fly to / hold Vicon waypoints |

Control laws and math live in helper files (`commander/control.py`, `pose.py`) and are tested in `tests/more_examples/`.
Overview: [more_examples/README.md](../more_examples/README.md).

## Copy one

```bash
cp -r projects/examples/feature_aruco projects/my_aruco      # Windows: xcopy /E /I ...
```

Then rename the class in `commander/main.py` to `my_aruco` (class name = folder name) and run `python run.py run -n my_aruco`.
