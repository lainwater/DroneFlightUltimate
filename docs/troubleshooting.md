# Troubleshooting

## No answer from the Tello

Symptom: `ack.drone1: {'cmd': 'connect', 'ack': 'None', 'info': 'No answer from ...'}`. Nothing works afterwards.

Not one UDP packet came back. Almost never the drone or the code:

1. **Firewall (most common, Windows).** If you ever clicked "Cancel" on the Python firewall prompt, Windows created
   a *block* rule for python.exe, and it drops every reply. Open `wf.msc` → *Inbound Rules*, delete red "python"
   rules, allow inbound UDP **9000, 8890, 11111**. A network set to "Public" is also stricter; set it to "Private".
2. **Wrong network / IP.** `ping <tello ip>`. Hotspot mode = `192.168.10.1` with the PC on `TELLO-xxxxxx`.
   Station mode = the IP from your router, PC on the same network and subnet (guest Wi-Fi often isolates devices).
3. **Port in use.** Another program (or a second project, or an old script) uses 9000/8890/11111.
4. **Wrong device.** In the Vicon lab `192.168.10.1` is often the Vicon PC, not a Tello.

## Connected, but no video

- Firewall: inbound UDP **11111** (see above).
- Press **J** (drone video). The window opening (`start_stream`) is not the same as the drone sending video.
- `ModuleNotFoundError: av`: `pip install av` (a DFU dependency, decodes the Tello video).
- simdrone: `CameraOpenFailed` → camera used by another app (Teams, browser) or wrong `camera_index`.

## Keyboard does nothing / wrong keys

- `Keyboard layout 'qwertz' not found`: layouts are now `keyboard` / `keyboard_video`. Change `[controller] layout` in `defaults.toml`.
- Keys are read system-wide; on macOS allow the terminal under *Privacy → Accessibility / Input Monitoring*.
- Commands answered with `error.drone1 Not connected / Not armed`: press **C**, then **V** before **T**.
- `error NotSupported ... needs tello_edu / tello_talent`: your `"model"` can't do that command ([Tello models](tello_models.md)).
  Wrong model set? Fix `"model"` in `config/mydrone.json`.

## T8L / joystick

- `RuntimeError: No joystick/gamepad found`: plug it in and turn it on before starting.
- A switch does nothing at start: switches act on *change*; the start position is not a command.

## Video features

| Message | Fix |
|---|---|
| `No camera calibration set` | `[video] calibration = "tello"` in defaults.toml (or `calibration=` in `get_videostream`) |
| `undistort paused: calibration 'tello' is for 960x720, frame is 320x240` | downward camera / other resolution; calibrate that camera |
| ArUco: markers found, distances wrong | `aruco_marker_size` = black square edge in **metres**; check the calibration (`tools.calibration list`, RMS < 1 px) |
| ArUco: no markers | wrong `aruco_dictionary`, marker too small/blurry, no white border around it |
| `Could not load YOLO model` / `No module named 'ultralytics'` | `pip install -U ultralytics` into the interpreter shown in the message |
| Everything lags | too much console output: exclude `data.stream.*`, `display.*`, `vicon.*` from the logger |

## Patterns / several drones

- Pattern status `aborted`: the drone reported an error meanwhile (not flying? Tello said `error`, e.g. a `go` with all
  axes under 20 cm). The `info` says which.
- `ValueError: move ... is too short`: make the pattern bigger (Tello `go` needs one axis ≥ 20 cm).
- Second Tello doesn't connect / no telemetry: every drone needs its own `cmd_pc_port`, `state_port`, `video_port`.
  Allow all of them in the firewall.

## Vicon

- `ModuleNotFoundError: vicon_dssdk`: install from the Vicon SDK folder (not on PyPI).
- `ConnectFailed`: Tracker running? `host` = Tracker PC `ip:801`, same network.
- `InvalidSubjectName` / always occluded: `subject` must match the name in Tracker exactly; object visible and enabled.

## Other

- `python run.py run -e -n <typo>` lists the available examples (it no longer creates an empty project).
- Every run's full bus log is in `logs/bus_logs/flight_<date>.jsonl`. Search it for `error`.
