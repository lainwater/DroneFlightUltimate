# Projects

A project is a folder with your code and its configuration:

```text
projects/my_project/
├── commander/
│   ├── __init__.py
│   └── main.py          class my_project(ProjectBase)  - class name = folder name
├── config/
│   ├── defaults.toml    controller layout, [video], [vicon], your own settings
│   └── mydrone.json     which drone(s)
└── logs/                created automatically
    ├── bus_logs/        flight_<date>.jsonl - every bus message of every run
    └── media/           drone1_<date>.mp4 recordings, drone1_<date>.jpg snapshots
```

## run.py

```bash
python run.py create -n my_project        # new project from the template (simdrone + keyboard)
python run.py run -n my_project           # projects/my_project
python run.py run -e                      # list examples
python run.py run -e -n tello_keyboard    # projects/examples/tello_keyboard
python run.py run -m                      # list more_examples
python run.py run -m -n tello_patterns    # more_examples/tello_patterns
python run.py run -n my_project -p D:/elsewhere   # project in another folder
```

Short forms: `c` = `create`, `r` = `run`. From Python: `run.create_project(name)`, `run.run_project(name, _type="example")` (or `"more"`).

The project class should have the folder's name. If it doesn't, the one `ProjectBase` subclass in `main.py` is used.
**Helper files** next to `main.py` (e.g. `commander/control.py`) are imported by name: `from control import Gains`.

## main.py

```python
import asyncio

from core.controller import ControllerType, get_controller
from core.logger import LoggerType, get_logger
from core.video import VideoOutputType, get_videostream
from projects.base import ProjectBase


class my_project(ProjectBase):
    async def setup(self) -> None:
        self.live_logger = get_logger(LoggerType.LIVE_CONSOLE, min_level=self.log_level)
        self.recorder.attach(self.bus)  # flight log to logs/bus_logs/
        self.bus.subscribe("*", self.live_logger.log_bus_event)

        self.drone1 = self.create_drone("drone_1")  # from config/mydrone.json
        self.video1 = get_videostream(
            VideoOutputType.CV2, drone_id=self.drone1.drone_id, bus=self.bus, media_dir=self.log_dir / "media", **self.app_config.get("video", {})
        )
        layout = self.app_config.get("controller", {}).get("layout")
        self.controller = get_controller(ControllerType.KEYBOARD, drone_id=self.drone1.drone_id, bus=self.bus, layout=layout)

        self.bus.subscribe("project.drone1", self.on_key)  # keys 9 / 0

    async def main(self) -> None:
        await self.controller.start_controller()
        await self.video1.start_stream()
        print(self.controller.controls_text())
        await asyncio.Event().wait()  # run until CTRL+C

    async def on_key(self, topic: str, data: dict) -> None:
        if data["action"] == "misc_1":
            await self.bus.publish("cmd.drone1", {"action": "rotate_cw", "args": {"degrees": 45}})

    async def end_run(self) -> None:  # always runs, also after CTRL+C / errors
        await self.shutdown_drone(self.drone1)
        if self.video1.is_running:
            await self.video1.stop_recording()
            await self.video1.stop_stream()
        await self.controller.stop_controller()
        self.recorder.detach(self.bus)
```

Bus handlers may be `async def` or plain `def`; both get `(topic, data)`.

## ProjectBase reference

| Member | |
|---|---|
| `self.bus` | the bus of this run |
| `self.app_config` | `config/defaults.toml` as dict |
| `self.drone_config` | `config/mydrone.json` as dict |
| `self.recorder` | flight recorder; `attach(bus)` / `detach(bus)`; `exclude_topics` (default `("frame.*",)`) |
| `self.log_dir` | `<project>/logs` |
| `self.log_level` | `[logging] level` from defaults.toml as `LogLevel` (default INFO) |
| `self.root_path` | the project folder |
| `self.create_drone(key="drone_1")` | drone from `mydrone.json[key]`: `drone_type` + `drone_id` choose it, **every other field is passed to the drone** (`ip`, `port`, `camera_index`, `cmd_pc_port`, ...) |
| `await self.shutdown_drone(drone)` | stop video → land (if flying) → disconnect → detach, each step even if the one before failed |
| `setup()` / `main()` / `end_run()` | yours to write (all three required) |

## config/mydrone.json

```json
{
  "drone_1": { "drone_type": "dji_tello", "drone_id": "drone1", "ip": "192.168.10.133" },
  "drone_2": { "drone_type": "sim_simdrone", "drone_id": "drone2", "camera_index": 0 }
}
```

| Field | Drone | Default |
|---|---|---|
| `drone_type` | all | `dji_tello` or `sim_simdrone` |
| `model` | Tello | `tello`, `tello_edu`, `tello_talent` (unset = no capability checks) - [Tello models](tello_models.md) |
| `drone_id` | all | used in every topic (`cmd.<drone_id>`) |
| `ip` | Tello | `192.168.10.1` (Tello hotspot) |
| `cmd_port`, `cmd_pc_port`, `state_port`, `video_port` | Tello | 8889, 9000, 8890, 11111 |
| `ip`, `port` | simdrone | `67.67.0.1`, `6767` (not used for anything real) |
| `camera_index` | simdrone | `0` - laptop camera used as its video |

Two Tellos in one program need different `cmd_pc_port`/`state_port`/`video_port` (sent to the drone on connect):
[several Tellos](tello_models.md#several-tellos-at-once), example `more_examples/edu_multi_tello`.

## config/defaults.toml

```toml
[logging]
level = "INFO"                  # DEBUG | INFO | WARNING | ERROR (console log)

[controller]
layout = "keyboard_video"       # keyboard | keyboard_video | t8l_pos | t8l_video

[video]                         # passed as keyword arguments to get_videostream()
calibration = "tello"           # core/video/calibration/tello.npz (undistort + ArUco pose)
aruco_dictionary = "DICT_5X5_50"
aruco_marker_size = 0.15        # metres, black square edge
aruco_publish = true            # ArUco results on data.stream.<drone_id>

[vicon]                         # read by feature_vicon
host = "192.168.10.1:801"
subject = "tello-1"
rate_hz = 20

[my_stuff]                      # anything you like: self.app_config["my_stuff"]
speed = 0.4
```

## Patterns

**Send a command from code:** `await self.bus.publish("cmd.drone1", {"action": "takeoff"})`. Commands
that need a state (connected, armed, landed) answer `error.drone1` `Not connected` etc. instead of doing something.

**Fly a pattern:** `patterns = get_patterns("drone1", self.bus)`, `patterns.start(patterns.square(100))`, `await patterns.cancel()`.
See [patterns](modules/patterns.md).

**Wait for an answer:** subscribe to `data.drone1` (or `ack.drone1`) and react there. See `examples/feature_project_commands`.

**Show your numbers on the video:** `await self.bus.publish("display.drone1", {"dist": 1.23, "R": matrix})`.
Lists and numpy matrices are drawn row by row. Each message replaces the previous block.

**Use detections:** `start_detection(publish=True)` / `aruco_publish = true`, then subscribe to `data.stream.drone1`.
Keep these and `display.*`, `vicon.*` out of the console: `get_logger(..., exclude_topics=("frame.*", "data.stream.*", "display.*"))`.

**Don't block the loop:** everything runs in one asyncio event loop. Long computations go in
`await asyncio.to_thread(fn, ...)`; never `time.sleep()` in a handler, use `await asyncio.sleep()`.
