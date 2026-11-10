# Concepts

## The idea

DroneFlightUltimate (DFU) is an async Python framework for flying drones from small "projects".
Every part is a module with a fixed interface (`base.py`) and swappable implementations:

```
              keyboard / joystick                     your project code
                     │ cmd.drone1                           │ cmd.* / display.* / ...
                     ▼                                      ▼
  ┌──────────────────────────────── BUS (publish / subscribe) ────────────────────────────────┐
  └─────▲──────────────▲────────────────▲──────────────────▲─────────────────▲────────────────┘
        │ ack/state/   │ frame.drone1   │ data.stream.*    │ vicon.drone1    │ "*" (everything)
        │ data/error   │                │                  │                 │
     drone (Tello,   video window     YOLO / ArUco       Vicon receiver   console logger,
     simdrone)       (cv2)            (inside video)                      flight recorder (.jsonl)
```

**No module imports another module.** They only publish and subscribe topic strings on the bus. That is
why you can swap the keyboard for a joystick, or the Tello for the simdrone, by changing one line or
config value, and why a recorded flight can be replayed: the recording *is* the bus traffic.

## Module overview

| Module | Factory | Implementations |
|---|---|---|
| `core.bus` | `get_bus()` | `SimpleBus` |
| `core.drone` | `get_drone(DroneType, drone_id, bus=..., **config)` | `DJI_TELLO`, `SIM_SIMDRONE` |
| `core.controller` | `get_controller(ControllerType, drone_id, bus, layout)` | `KEYBOARD`, `JOYSTICK` |
| `core.video` | `get_videostream(VideoOutputType, drone_id, bus, **options)` | `CV2` |
| `core.patterns` | `get_patterns(drone_id, bus)` | flight patterns over the bus |
| `core.vicon` | `get_vicon(drone_id, bus, host=..., subject=...)` | Vicon DataStream SDK |
| `core.logger` | `get_logger(LoggerType, min_level, ...)` | `LIVE_CONSOLE`, `JSONL`, `NOLOGGER` |
| `core.bus_player_recorder` | `get_recorder(path)`, `get_player(path)` | JSON-Lines |
| `core.fileops` | `get_fileops()` | Windows / Linux / macOS |

Always import through the factory (`from core.drone import get_drone`), never an implementation file directly.

## Messages

A topic is `<kind>.<drone_id>` or `<kind>.<module>.<drone_id>`. The data is a dict.

Commands always have the same shape:

```python
await bus.publish("cmd.drone1", {"action": "takeoff"})
await bus.publish("cmd.drone1", {"action": "rc", "args": {"x": 0, "y": 0.5, "z": 0, "yaw": 0}})
await bus.publish("cmd.stream.drone1", {"action": "start_aruco", "args": {"marker_size": 0.10}})
```

The receiver looks `action` up in its `commands.json`, which maps it to a method and default `args`.
Your `args` override the defaults. Unknown actions answer with `error.<...>` `NotCapable`, actions the drone model
can't do with `NotSupported`. Extra keys are ignored. `core.patterns` adds `"source": "patterns"`, so a project can
tell its own or the patterns' commands from keyboard commands.

## Bus topics

`drone1` stands for any `drone_id`. "→" = who publishes → who listens.

| Topic | Direction | Data |
|---|---|---|
| `cmd.drone1` | controller / project → drone | `{"action", "args"?}` - see [drone commands](modules/drone.md#commands) |
| `ack.drone1` | drone → | `{"cmd", "ack": "True" \| "False" \| "unknown" \| "None", "info"?}` |
| `error.drone1` | drone → | `{"error", "message", "action"?}` |
| `data.drone1` | drone → | answer of a `get_*`, e.g. `{"battery": 87}` |
| `state.drone1` | drone → | telemetry after `start_state_receiver`, same keys for every drone: `{"battery", "height", "attitude", "position", ...}` ([list](modules/drone.md#telemetry)) |
| `frame.drone1` | drone → video | `{"ts", "seq", "encoding": "bgr24", "frame": ndarray}` |
| `cmd.stream.drone1` | controller / project → video | `{"action", "args"?}` - see [video commands](modules/video.md#commands) |
| `ack.stream.drone1`, `error.stream.drone1` | video → | like the drone's |
| `data.stream.drone1` | video → | `{"detections": [...]}` (YOLO, if `publish=True`) or `{"aruco": [...]}` (if `aruco_publish`) |
| `display.drone1` | project → video | `{"label": value, ...}` drawn top-right; `{}` clears it |
| `project.drone1` | controller → project | `{"action": "misc_1"}` from layout entries with `"target": "project"` |
| `ack.patterns.drone1` | patterns → | `{"pattern", "status": started / done / cancelled / aborted, "info"?}` |
| `vicon.drone1` | vicon → | `{"ts", "frame", "subject", "occluded", "x", "y", "z", "roll", "pitch", "yaw", "qx".."qw"}` |
| `ack.vicon.drone1`, `error.vicon.drone1` | vicon → | connect / errors |
| `error.bus` | bus → | a subscriber raised: `{"topic", "errors"}` |
| `error.Keyboard.drone1` | keyboard → | key lookup failed |
| `state.joystick-<layout>.drone1`, `error.joystick-<layout>.drone1` | joystick → | connected / errors |

**Wildcards:** only `"*"` (everything). `bus.subscribe("error.*", ...)` subscribes to a topic literally
named `error.*` and never fires. To catch all errors, subscribe to `"*"` and filter `topic.startswith("error")`.
(The logger and recorder *exclude* lists do use patterns like `frame.*`; that is their own filter.)

## Lifecycle of a project

`python run.py run -n my_project` → `projects/__init__.get_project()` loads `commander/main.py` and
creates the class with the folder's name. Then `ProjectBase.run()`:

1. `setup()`: create logger, drone, video, controller, subscribe your handlers
2. `main()`: start things, then usually `await asyncio.Event().wait()` (= run until CTRL+C)
3. `end_run()`: **always** called, also after CTRL+C or an error: land, disconnect, close windows

Every run writes the complete bus traffic (except video frames) to `logs/bus_logs/flight_<date>.jsonl`.

## Coordinate frames

| Where | Frame |
|---|---|
| `rc` command | `x` right, `y` forward, `z` up, `yaw` clockwise; each -1.0 ... 1.0 |
| `goto` / `curve` | Tello "go" frame, relative: `x` forward, `y` **left**, `z` up; cm |
| telemetry `position` | `x` right, `y` forward, `z` up from the takeoff spot; cm |
| ArUco marker pose | OpenCV camera frame: `x` right, `y` down, `z` forward out of the lens; metres |
| Vicon | Vicon world frame of the lab, millimetres; roll/pitch/yaw = extrinsic xyz in degrees |

## File structure

```text
.
├── run.py                      CLI: create / run projects
├── core/
│   ├── bus/                    publish/subscribe
│   ├── bus_player_recorder/    flight logs (.jsonl) + replay
│   ├── controller/
│   │   └── implementations/
│   │       ├── keyboard_controller/   keyboard.json, keyboard_video.json
│   │       └── joystick_controller/   t8l_pos.json, t8l_video.json
│   ├── drone/
│   │   ├── telemetry.py        unified telemetry keys + units
│   │   └── implementations/
│   │       ├── DJI/tello/      commands.json, tello.py, tellosdk.py
│   │       └── Sim/simdrone/   commands.json, simdrone.py, simdronesdk.py
│   ├── fileops/
│   ├── logger/
│   ├── patterns/               flight patterns (square, orbit, lawnmower, ...)
│   ├── vicon/
│   └── video/
│       ├── calibration/        <camera>.npz + loader
│       └── implementations/cv2/   cv2_display.py, vision.py, commands.json, yolo26n.pt
├── projects/
│   ├── base.py                 ProjectBase
│   ├── examples/               12 basic + feature examples
│   └── <your_project>/         commander/main.py, config/, logs/
├── more_examples/              11 task-style projects (python run.py run -m -n <name>)
├── tools/                      standalone (no DFU imports)
│   ├── set_tello_wifi.py
│   ├── count1.ps1
│   └── calibration/            capture -> calibrate -> verify
├── tests/
└── docs/
```
