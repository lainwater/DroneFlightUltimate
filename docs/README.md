# DroneFlightUltimate docs

| Read this | when you want to |
|---|---|
| [Getting started](getting_started.md) | install, fly the simdrone, then a real Tello |
| [Tello models](tello_models.md) | basic / EDU / Talent, hotspot vs. station mode, several Tellos at once |
| [Concepts](concepts.md) | understand the bus, the modules and every bus topic |
| [Projects](projects.md) | write your own project (`setup` / `main` / `end_run`, config files, `run.py`) |
| [Examples](examples.md) | what each example and more_example shows |
| [Troubleshooting](troubleshooting.md) | fix "no connection", "no video", layout errors, ... |
| [Contributing](contributing.md) | dev setup, tests, adding a drone/controller/video feature |

Module reference:

| Module | |
|---|---|
| [bus](modules/bus.md) | async publish/subscribe - everything talks through it |
| [drone](modules/drone.md) | DJI Tello + simdrone: commands, unified telemetry, frames |
| [controller](modules/controller.md) | keyboard + joystick (RadioMaster T8L), layout files |
| [patterns](modules/patterns.md) | predefined flight patterns: polygons, circle, orbit, lawnmower, waypoints, dance |
| [video](modules/video.md) | video window, overlays, recording, YOLO, ArUco, undistort, calibration |
| [vicon](modules/vicon.md) | Vicon motion capture pose on the bus |
| [logger + recorder/player](modules/logging.md) | console log, flight logs on disk, replay |
| [fileops](modules/fileops.md) | small OS-independent file helpers |
| [tools](tools.md) | `set_tello_wifi`, camera calibration |
