# Getting started

## 1. Install

Python 3.11 or newer.

```bash
git clone https://github.com/lainwater/DroneFlightUltimate
cd DroneFlightUltimate
python -m venv .venv
.venv\Scripts\activate          # Windows   (Linux/macOS: source .venv/bin/activate)
pip install -e .                # ".[yolo]" adds YOLO (ultralytics, large), ".[all]" also pytest + ruff
```

Optional, only for the Vicon motion capture system: `vicon_dssdk` is not on PyPI. Install it from the
Vicon DataStream SDK folder (`install_vicon_dssdk.bat`, or `pip install "<SDK>\Python\vicon_dssdk"`).

Every command below is run from the repository root.

Which Tello do you have (basic / EDU / Talent)? Set it as `"model"` in `config/mydrone.json`. See [Tello models](tello_models.md).

## 2. Fly the simdrone (no hardware)

```bash
python run.py run -e                          # list the examples
python run.py run -e -n simdrone_keyboard
```

The controls are printed at start. Press **C** (connect), **V** (arm), **T** (takeoff), fly with
**W A S D** and the arrow keys, then **L** (land). The console shows every bus message, for example
`ack.drone1: {'cmd': 'takeoff', 'ack': 'True'}`. **CTRL+C** quits; the drone lands and disconnects on its own.

> The keyboard is read system-wide: keys work even when the console is not focused. Don't type in
> other windows while a project is running.

`simdrone_keyboard_video` does the same with a video window. The simdrone's "camera" is your laptop
camera: press **J** for video, **7** to undistort it, **5** for ArUco markers.

## 3. Fly a DJI Tello

**Tello hotspot (simplest):** turn the Tello on, connect your PC to its Wi-Fi `TELLO-xxxxxx`, then

```bash
python run.py run -e -n tello_keyboard_video
```

Press **C**, then **J** for video. Default IP is `192.168.10.1`.

**Tello on your own network (station mode, Tello EDU / Tello Talent only):** lets several drones,
the Vicon PC and the internet live on one network.

```bash
python -m tools.set_tello_wifi --ssid YOUR_WIFI --password YOUR_PASSWORD
```

The Tello reboots onto your network. Find its IP in your router (e.g. `192.168.10.133`) and put it in the
project's `config/mydrone.json` as `"ip"`. Your PC must be on the same network.

Nothing happens on **C**? See [Troubleshooting](troubleshooting.md#no-answer-from-the-tello). It is
almost always the PC firewall.

## 4. Your own project

```bash
python run.py create -n my_project      # creates projects/my_project/
python run.py run -n my_project
```

Edit `projects/my_project/commander/main.py`. Copying from an example is the fastest way to start.
See [Projects](projects.md). `projects/*` (except `examples/`) is ignored by git, so your projects stay yours.

## 5. Next

- [Concepts](concepts.md): how the modules talk to each other (5 minutes, worth it)
- [Video](modules/video.md): YOLO, ArUco, undistort, recording
- [Tools](tools.md): calibrate a new camera
- `python run.py run -m`: [more_examples](examples.md#more_examples-bigger-task-style-projects), e.g. patterns, fly to a marker, search and rescue, several drones
