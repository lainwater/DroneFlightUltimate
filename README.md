# Drone Flight Ultimate

> Modular, async Python framework to fly drones (the DJI Tello family, a built-in simulator) with keyboard, joystick
> or your own code: live video, object detection, ArUco markers, flight patterns and Vicon motion capture, all wired
> together through one event bus.

- **Drones:** Tello, Tello EDU, Tello Talent (RoboMaster TT), one or several at once, and a simdrone that needs no hardware (its video is your laptop camera)
- **Control:** keyboard (any layout), RadioMaster T8L / gamepad, predefined flight patterns, or your own closed loop (ArUco, Vicon)
- **Video:** overlays, recording, snapshots, FPV goggles mode, YOLO, ArUco detection + localization, lens undistortion
- **Lab:** Vicon pose on the bus, camera calibration tool, Tello Wi-Fi (station mode) setup
- **Telemetry:** the same keys and units for every drone (`battery`, `height`, `attitude`, `mission_pad`, ...)
- **Logs:** every flight's complete bus traffic as `.jsonl`, replayable

**Docs: [docs/](docs/README.md)**: [Getting started](docs/getting_started.md) · [Tello models](docs/tello_models.md) · [Concepts](docs/concepts.md) ·
[Projects](docs/projects.md) · [Examples](docs/examples.md) · [Troubleshooting](docs/troubleshooting.md) · [Contributing](docs/contributing.md)

---

## Table of Contents
- [Quick start](#quick-start)
- [Controls](#controls)
- [Your own project](#your-own-project)
- [Examples](#examples)
- [Flight patterns](#flight-patterns)
- [Tools](#tools)
- [How it works](#how-it-works)
- [To-Do](#to-do)
- [Contributors & Licensing](#contributors--licensing)

---

## Quick start

Python 3.11+. Run everything from the repository root.

```bash
git clone https://github.com/lainwater/DroneFlightUltimate
cd DroneFlightUltimate
python -m venv .venv && .venv\Scripts\activate       # Linux/macOS: source .venv/bin/activate
pip install -e .                                      # ".[yolo]" adds YOLO, ".[all]" also pytest + ruff

python run.py run -e                                  # list the examples
python run.py run -e -n simdrone_keyboard             # fly the simulator: C connect, V arm, T takeoff, WASD + arrows
```

Real Tello: connect the PC to the Tello's Wi-Fi, then `python run.py run -e -n tello_keyboard_video` (C, then J for video).
Tello EDU / Talent on your own network: `python -m tools.set_tello_wifi --help`, then put its IP in the project's
`config/mydrone.json`, together with `"model"` (`tello`, `tello_edu`, `tello_talent`): [Tello models](docs/tello_models.md).

No connection? It's almost always the PC firewall: see [Troubleshooting](docs/troubleshooting.md#no-answer-from-the-tello).

Vicon only: install `vicon_dssdk` from the Vicon DataStream SDK folder (not on PyPI).

## Controls

Keyboard layouts `keyboard` and `keyboard_video` (set in `config/defaults.toml`). The same keys work on QWERTZ and
QWERTY. Every project prints its controls at start.

| Keys | Action | Keys | Action |
|---|---|---|---|
| W / S | up / down | T / L | takeoff / land |
| A / D | yaw left / right | **Space** | **EMERGENCY** (motors off) |
| arrows | forward / back / left / right | C | connect |
| V / B | arm / disarm | I / O | telemetry on / off |
| U / P | get attitude / position | 9 / 0 | misc_1 / misc_2 → your project |
| *video layout:* | | | |
| J / K | drone video on / off | 1 / 2 | forward / downward camera |
| 3 / 4 | YOLO on / off | 5 / 6 | ArUco on / off |
| 7 / 8 | undistort on / off | N / M | stats overlay on / off |
| F / G | FPV goggles on / off | E / R | record start / stop |
| Q | snapshot | | |

RadioMaster T8L: layouts `t8l_pos` and `t8l_video`, see [controller docs](docs/modules/controller.md#joystick-radiomaster-t8l-or-any-pygame-gamepad).

## Your own project

```bash
python run.py create -n my_project     # projects/my_project/ (simdrone + keyboard template)
python run.py run -n my_project
```

```text
projects/my_project/
├── commander/main.py       class my_project(ProjectBase): setup() / main() / end_run()
├── config/defaults.toml    layout, [logging], [video], your own settings
├── config/mydrone.json     drone type, id, ip, ...
└── logs/                   bus_logs/flight_<date>.jsonl, media/*.mp4 *.jpg
```

Talk to the drone by publishing on the bus:

```python
await self.bus.publish("cmd.drone1", {"action": "takeoff"})
await self.bus.publish("cmd.drone1", {"action": "rc", "args": {"x": 0, "y": 0.5, "z": 0, "yaw": 0}})
await self.bus.publish("display.drone1", {"distance [m]": 1.23})          # text on the video
self.bus.subscribe("data.stream.drone1", self.on_markers)                  # ArUco / YOLO results
```

Full guide: [docs/projects.md](docs/projects.md). Your projects in `projects/` are ignored by git.

## Examples

**Basics and features** in `projects/examples/`: `python run.py run -e -n <name>`. Details: [docs/examples.md](docs/examples.md)

| Example | |
|---|---|
| `simdrone_keyboard`, `simdrone_keyboard_video` | simulator + keyboard (video = laptop camera) |
| `simdrone_t8l`, `simdrone_t8l_video` | simulator + RadioMaster T8L |
| `tello_keyboard`, `tello_keyboard_video` | Tello + keyboard |
| `tello_t8l`, `tello_t8l_video` | Tello + RadioMaster T8L |
| `feature_project_commands` | your own keys (9/0) → your code → overlay |
| `feature_aruco` | ArUco markers detected + localized, undistorted video |
| `feature_yolo` | YOLO object detection |
| `feature_vicon` | Vicon pose on the video |

**Task-style projects** in `more_examples/`: `python run.py run -m -n <name>`. The prefix says which drone is needed:
`sim_` none · `tello_` any Tello · `edu_` Tello EDU / Talent · `talent_` Talent with expansion kit · `vicon_` Vicon lab.

| more_examples | |
|---|---|
| `sim_yolo` | everything auto-started on the simdrone |
| `tello_patterns`, `tello_command_test` | flight patterns on key 9; step through all commands (skips what your model can't do) |
| `fly_to_marker` | closed loop: hold 1 m in front of an ArUco marker |
| `edu_pad_pose_orbit`, `edu_search_and_rescue` | mission pads: pose on a board, orbit, dance; lawnmower search and landing on the target pad |
| `edu_multi_tello` | several Tellos with one keyboard, patterns in parallel |
| `talent_cooling_battery_gauge`, `talent_tof_ruler` | expansion kit: cooling + battery gauge on the dot matrix; ToF ruler |
| `vicon_yolo`, `vicon_position_control` | Vicon pose on the video; closed loop: fly to / hold Vicon waypoints |

## Flight patterns

```python
from core.patterns import get_patterns
patterns = get_patterns("drone1", self.bus)
await patterns.square(side_cm=100)                 # also triangle, hexagon, circle, rectangle, waypoints, lawnmower, spin
patterns.start(patterns.orbit(radius_cm=100))      # in the background (nose to the centre) ...
await patterns.cancel()                            # ... stop: the drone hovers
```

They fly with normal drone commands over the bus, so they work on every Tello and the simdrone. [docs/modules/patterns.md](docs/modules/patterns.md)

## Tools

Standalone (no DFU imports, only opencv-python + numpy):

```bash
python -m tools.set_tello_wifi --ssid <wifi> --password <pw>          # Tello EDU / Talent joins your Wi-Fi
python -m tools.calibration capture | calibrate | verify | list       # camera calibration
powershell -File tools/count1.ps1                                     # lines of code per folder
```

See [docs/tools.md](docs/tools.md).

## How it works

Every module (drone, controller, video, Vicon, logger, recorder) only publishes and subscribes **topics** on one async
**bus**. No module imports another. So the keyboard can be swapped for a joystick, the Tello for the simulator, and a
recorded flight can be replayed.

```
keyboard ──cmd.drone1──▶ ┌─────┐ ──cmd.drone1──▶ drone ──frame.drone1──▶ video window (YOLO, ArUco)
your code ─────────────▶ │ BUS │ ◀──ack/data/state/error── drone        ──data.stream.drone1──▶ your code
Vicon ──vicon.drone1───▶ └─────┘ ──"*"──▶ console logger, flight recorder (.jsonl)
```

All topics and message formats: [docs/concepts.md](docs/concepts.md). Module reference: [docs/modules/](docs/README.md).

---

## To-Do

### Done recently
- [x] Flight patterns module (`core/patterns`): polygons, circle, rectangle, waypoints, lawnmower, spin, orbit, dance; cancel + abort
- [x] Tello models (basic / EDU / Talent) with capability checks; several Tellos at once (per-drone ports)
- [x] Unified telemetry: same keys and units for Tello and simdrone, in `state.*` and `data.*`
- [x] `more_examples/`: 11 task-style projects incl. fly-to-marker and Vicon position control (closed loops), search and rescue, multi-Tello
- [x] Standalone tools (Tello Wi-Fi, camera calibration), `count1.ps1`
- [x] Tests for every module (180, no hardware needed: fake Tello over UDP, fake Vicon, headless video)
- [x] simdrone: picks its flight mode itself, moves relative to its nose, relative `goto`, `stop`, `rotate`
- [x] Tello: `stop` interrupts a running move, position estimate follows the heading
- [x] Earlier: camera calibration, undistort, ArUco, YOLO, Vicon, keyboard layouts, all basic examples, docs

### Important
- [ ] Re-capture the `tello` and `webcam` calibrations (RMS 2.3 / 3.5 px, target < 1 px; board bigger in the frame and stiff)
- [ ] Fly-test on real drones: `fly_to_marker` and `vicon_position_control` gains, orbit calibration (`cms_per_rc`, `deg_per_s_per_rc`)
- [ ] GitHub: CI (lint + tests), issue tags, versions
- [ ] Standardized docstrings everywhere

### Less important
- [ ] Patterns: `curve`-based circles (Tello only), formation flying with several drones (offsets per drone)
- [ ] T8L layouts: misc_1 / misc_2 on free switches, record/snapshot in `t8l_video`
- [ ] REPL controller (type commands) + examples
- [ ] Web-server video output (`VideoOutputType.WEBSERVER` is a stub)
- [ ] Use `solve_localization_2D` (2-point localization) or drop it
- [ ] Presentations (users, contributors, non-tech), present to the professors, make the repo public

### Future
- [ ] Rework the error pipeline, more standardized bus message format
- [ ] Web UI / app for managing projects
- [ ] More controllers (gamepads) and drones (Parrot Mambo, BetaFPV, ...)

### Known issues
- A rare async timing bug that hasn't been reproduced yet.
- Tello acks over UDP get lost sometimes (`"ack": "unknown"`); DFU assumes the command worked.
- The Tello's `position` is an estimate from the commands sent (no sensor for x/y without mission pads).
- The keyboard is read system-wide (also when another window is focused).
- `webcam.npz` fits only the laptop camera it was made with; calibrate yours.

---

## Contributors & Licensing
Initiated and maintained by `Valerie Lain`. Contributing: [docs/contributing.md](docs/contributing.md).
License: [LICENSE](LICENSE). Free to use, copy and modify, not for sale; the license must stay with every copy.
