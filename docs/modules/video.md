# core.video

Shows `frame.<drone_id>` in an OpenCV window, draws overlays, records, and runs YOLO / ArUco / undistortion.

```python
from core.video import VideoOutputType, get_videostream

video = get_videostream(VideoOutputType.CV2, drone_id="drone1", bus=bus,
                        media_dir=project.log_dir / "media",      # recordings + snapshots
                        calibration="tello")                       # optional, see below
await video.start_stream()       # opens the window; the DRONE's video is started separately (start_video / key J)
...
await video.stop_stream()
```

The window only shows something once the drone sends frames (`cmd.drone1` `start_video`).
Frames are fitted into 960x720 (aspect kept), so the small downward camera is enlarged.

## Options (`get_videostream` keyword arguments = `[video]` in defaults.toml)

| Option | Default | |
|---|---|---|
| `media_dir` | `./logs/media` | where `.mp4` / `.jpg` go |
| `calibration` | none | name in `core/video/calibration/` (`tello`, `webcam`) or a path to an `.npz` |
| `aruco_dictionary` | `DICT_5X5_50` | must match your printed markers |
| `aruco_marker_size` | `0.15` | **black square edge in metres**; a wrong value scales every distance |
| `aruco_publish` | `false` | publish marker results on `data.stream.<id>` |

## Commands

`cmd.stream.<drone_id>` `{"action", "args"?}`, or call the method directly (`await video.start_aruco()`).

| Action | Args | |
|---|---|---|
| `start_video` / `stop_video` | | open / close the window |
| `show_state_on` / `show_state_off` | `data_to_display` (`["ts","fps","battery","height"]`, any [telemetry key](drone.md#telemetry)) | telemetry text top-left (needs `start_state_receiver`) |
| `show_custom_on` / `show_custom_off` | | the `display.<id>` block top-right |
| `set_custom_data`, `clear_custom_data` | `data` | same as publishing `display.<id>` |
| `fpv_on` / `fpv_off` | | side-by-side square image for FPV goggles |
| `rescale` | `scale` | extra zoom factor |
| `display_size` | `width, height` (960, 720) | box the video is fitted into |
| `auto_fit_on` / `auto_fit_off` | | off = native resolution |
| `start_recording` / `stop_recording` | | `drone1_<date>.mp4` (raw camera image, no overlays) |
| `take_snapshot` | | `drone1_<date>.jpg` (raw camera image) |
| `start_detection` / `stop_detection` | `model_path, conf (0.4), imgsz (640), classes, publish` | YOLO |
| `start_aruco` / `stop_aruco` | `dictionary, marker_size, publish, calibration` | ArUco markers |
| `undistort_on` / `undistort_off` | `calibration, alpha (1.0)` | remove lens distortion |

## Overlays

- top-left: drone id, and the stats with `show_state_on`
- top-right (yellow): your data from `display.<id>`. Numbers, strings, lists and numpy matrices (one line per row). Every message replaces the block.
- bottom-left: one status line per running feature (YOLO / ArUco / UNDISTORTED), so you can see it is running even when nothing is found.

## YOLO

`start_detection()` loads `yolo26n.pt` (next to `cv2_display.py`; otherwise ultralytics downloads it) and needs
`pip install -e ".[yolo]"` (or `pip install -U ultralytics`). Inference runs in a thread, one frame at a time. Frames arriving meanwhile are shown
with the last boxes, so the video never stalls. With `publish=True` every result goes to `data.stream.<id>`:

```python
{"detections": [{"label": "person", "class_id": 0, "conf": 0.87, "box": (x1, y1, x2, y2)}]}
```

## Camera calibration

A calibration (`core/video/calibration/<name>.npz`) describes one camera's lens: focal length, centre, distortion.
It belongs to **one camera at one resolution**:

| Name | Camera | Size |
|---|---|---|
| `tello` | Tello forward camera | 960x720 |
| `webcam` | the laptop camera it was made with (simdrone video) | 640x480 |

A frame of another size (e.g. the Tello's downward camera, 320x240) is detected. Undistort pauses and ArUco runs
without pose, both shown in the status line. Your laptop camera is not the one `webcam.npz` was made with, so
calibrate your own: [tools](../tools.md#camera-calibration).

```python
from core.video.calibration import load_calibration
c = load_calibration("tello")       # .camera_matrix (3x3), .dist_coeffs (1x5), .image_size, .rms
```

## Undistort

`undistort_on()` (key 7) shows the image without lens distortion: straight lines become straight.
`alpha=1` keeps every pixel (curved black border), `alpha=0` crops to the valid area. YOLO and ArUco then run on
the undistorted image. Recordings and snapshots stay raw.

## ArUco markers

`start_aruco()` (key 5) finds markers of `aruco_dictionary` and draws outline, ID, distance and axes
(x red, y green, z blue). With a calibration each marker is **localized** relative to the camera.
`aruco_publish` sends:

```python
{"aruco": [{
    "id": 7,
    "center": [cx, cy], "corners": [[x, y] * 4],                # pixels
    "x": 0.05, "y": 0.02, "z": 1.01, "distance": 1.01,          # metres, camera frame: x right, y down, z forward
    "roll": 165.0, "pitch": 25.0, "yaw": 10.0,                  # degrees, extrinsic xyz (= scipy as_euler("xyz"))
    "rvec": [...], "tvec": [x, y, z],                           # OpenCV solvePnP result
}]}
```

A marker facing the camera straight on has roll ≈ ±180°. That is OpenCV's convention (marker z points out of the
marker, towards the camera). Print markers with any ArUco generator for the same dictionary, and measure the
black square for `aruco_marker_size`. Without calibration you get `id`, `center`, `corners` only.

Accuracy (rendered test scene, Tello calibration): ~1 cm at 1 m, ~5 cm at 2.5 m with a 15 cm marker.
It gets worse with a bad calibration, motion blur and small markers.

## Adding an output

Implement `VideoBase` (`core/video/base.py`) and add a `case` in `get_videostream`. A web-server output is planned
(`VideoOutputType.WEBSERVER` currently raises `NotImplementedError`).
