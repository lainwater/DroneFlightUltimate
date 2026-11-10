# core.drone

```python
from core.drone import DroneType, get_drone

drone = get_drone(DroneType.DJI_TELLO, "drone1", bus=bus, ip="192.168.10.133", model="tello_edu")
# in a project simply: self.drone1 = self.create_drone("drone_1")   (reads config/mydrone.json)
```

The drone listens on `cmd.<drone_id>` and answers on `ack.` / `error.` / `data.` / `state.` / `frame.<drone_id>`.
You normally don't call its methods directly. Publish commands instead, so the controller, your code, `core.patterns`
and a replayed log all work the same way.

| `DroneType` | config `drone_type` | What |
|---|---|---|
| `DJI_TELLO` | `dji_tello` | DJI / Ryze Tello, Tello EDU, Tello Talent (RoboMaster TT) over UDP |
| `SIM_SIMDRONE` | `sim_simdrone` | simulated drone (position, attitude, battery); video = laptop camera |

Tello models (`"model"` in mydrone.json): see [Tello models](../tello_models.md). A command your model can't do
answers `error NotSupported` instead of being sent. Without `"model"` nothing is blocked.

## States

Commands check the drone's state first and answer `error.drone1` (`Not connected`, `Not armed`, ...) if it doesn't fit.

- connection: `disconnected` → `connect` → `connected`
- arm: `disarmed` → `set_arm` → `armed` (**takeoff needs connected + armed + landed**)
- flight: `landed` → `takeoff` → `inair` → `land`

Acks: `"True"` (ok), `"False"` (drone said error), `"unknown"` (no reply in time; Tello UDP drops replies, DFU
assumes it worked), `"sent"` (`rc`, `stop`: no reply expected). `connect` with no reply at all answers `"None"`
with a checklist in `info`, see [Troubleshooting](../troubleshooting.md#no-answer-from-the-tello).

## Telemetry

Both drones use the **same keys and units**, in `state.<id>` (after `start_state_receiver`, ~10 Hz) and in the
answers of `get_*` on `data.<id>` (`get_battery` → `{"battery": 87}`). Defined in `core/drone/telemetry.py`.

| Key | Unit | Tello | simdrone |
|---|---|---|---|
| `battery` | % | ✓ | ✓ |
| `height` | cm | height sensor | simulated z |
| `temperature` | °C | the higher board sensor | ✓ |
| `temperature_low` | °C | the lower board sensor | |
| `attitude` | `{"pitch", "roll", "yaw"}` deg | ✓ | ✓ |
| `position` | `{"x", "y", "z"}` cm, x right, y forward, z up | **estimate**: dead reckoning from the commands sent, turned by the drone's yaw, z = height | simulated |
| `speed` | `{"x", "y", "z"}` | as reported | ✓ |
| `acceleration` | `{"x", "y", "z"}` | 0.001 g | |
| `tof` | cm | downward distance sensor | |
| `barometer` | m | ✓ | |
| `flight_time` | s | motors-on time | |
| `mission_pad` | `{"id"}`: -1 none, -2 detection off; with a pad `+ "x", "y", "z"` (cm), `"yaw"` (= `mpry[1]`), `"mpry"` - **as the Tello reports them** (its pad frame: rocket = +x, y to the right, yaw clockwise; the same frame `goto_mission_pad` uses). Standard right-handed conversion: `more_examples/edu_pad_pose_orbit/commander/pose.py` | EDU / Talent | |
| `flight_mode` | | | ✓ |

`get_height`, `get_tof`, `get_ext_tof` answer in cm, `get_temperature` the higher sensor in °C,
`get_flight_time` seconds, `get_acceleration` `{"x","y","z"}`. Only keys the drone reports are present.

## Frames

| Command | Frame |
|---|---|
| `rc` | x right, y forward, z up, yaw clockwise; each -1.0 ... 1.0. Keep sending; `0,0,0,0` = hover |
| `steps_move_*`, `rotate_*` | relative to the nose |
| `goto`, `curve` | the Tello "go" frame, relative: **x forward, y LEFT, z up** (cm), each axis ±500, not all within ±20 |
| `goto_mission_pad`, `jump`, `curve` with `mid` | the mission pad's frame |
| telemetry `position` | x right, y forward, z up, from the takeoff spot |

## Commands

`{"action": <name>, "args": {...}}`. Args shown are the defaults from `commands.json`, so you only send what you change.
Extra keys in the message (e.g. `"source"`) are ignored by the drone.

**Both drones**

| Action | Args |
|---|---|
| `connect`, `disconnect` | disconnect lands first if flying |
| `set_arm`, `set_disarm` | |
| `takeoff`, `land`, `emergency` | `emergency` = motors off immediately |
| `stop` | Tello: hover **right now**, interrupts a running move (sent without waiting for it) |
| `rc` | `x, y, z, yaw` -1.0 ... 1.0 |
| `steps_move_up/down/forward/backward/left/right` | `distance` cm (30) |
| `rotate_cw`, `rotate_ccw` | `degrees` (90) |
| `goto` | `x, y, z` cm, `speed` cm/s (50) |
| `start_video`, `stop_video` | frames on `frame.<id>` |
| `start_state_receiver`, `stop_state_receiver` | telemetry on `state.<id>` |
| `get_position`, `get_attitude`, `get_battery`, `get_temperature` | answer on `data.<id>` |
| `get_state`, `get_stats`, `get_command_map` | |

**Tello**, with the models that can do it (all = also the basic Tello):

| Action | Args | Models |
|---|---|---|
| `flip_left/right/forward/back` | | all |
| `curve` | `x1 y1 z1 x2 y2 z2 speed`, optional `mid` | all (`mid`: EDU, Talent) |
| `set_speed` | `speed` cm/s (50) | all |
| `set_own_wifi` | `ssid, password` of its own hotspot | all |
| `get_speed, get_flight_time, get_wifi_snr, get_height, get_temperature, get_attitude, get_barometer, get_acceleration, get_tof` | | all |
| `stop`, `goto_mission_pad`, `jump`, `set_mission_pad_on/off`, `set_mission_pad_direction` | | EDU, Talent |
| `connect_via_wifi` (station mode, use `tools.set_tello_wifi`), `set_ports` | | EDU, Talent |
| `get_sdk_version`, `get_serial_number`, `get_hardware` | | EDU, Talent |
| `set_camera_forward/downward`, `set_video_fps`, `set_video_bitrate`, `motor_on/off`, `throw_fly`, `reboot` | | EDU (firmware ≥ 02.05.01.17), Talent |
| `ext_led*`, `ext_matrix*`, `get_ext_tof`, `get_ext_version`, `get_wifi_version`, `get_ap`, `get_ssid`, `set_multi_wifi`, `set_wifi_channel` | | Talent (expansion kit) |

**simdrone only:** `set_takeoff_height`, `set_rc_speed`, `set_flight_mode`, `set_ip_and_port`, and the matching `get_*`,
`get_armed_status`, `get_state_gen_status`. The simdrone picks its flight mode (rc / steps / goto) automatically and
moves relative to its nose like a real drone.

The full list with all default args is each drone's `commands.json` (`"models"` lists who can do it).

## Tello network

| Port | Where | Config key | What |
|---|---|---|---|
| 8889 | Tello | `cmd_port` | commands |
| 9000 | PC | `cmd_pc_port` | replies to commands |
| 8890 | PC | `state_port` | telemetry |
| 11111 | PC | `video_port` | H.264 video (decoded with PyAV) |

The PC firewall must allow inbound UDP on these PC ports for Python. Different `state_port` / `video_port` than the
defaults are sent to the drone (`port` command) on connect; that's how several Tellos share one PC
([Tello models → several Tellos](../tello_models.md#several-tellos-at-once)).

## Adding a drone

1. `core/drone/implementations/<Vendor>/<name>/` with `<name>.py` (subclass `DroneBase`), `commands.json`, `stats.json`.
2. Add a `DroneType` value in `core/drone/base.py` and a `case` in `core/drone/__init__.get_drone`.
3. Publish the same topics and the **unified telemetry keys** (`core/drone/telemetry.py`), then every controller,
   pattern and project works unchanged. Optional: set `self.model` and `"models"` in commands.json for capability checks.
