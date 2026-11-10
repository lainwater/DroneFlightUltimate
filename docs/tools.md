# Tools

Helper programs in `tools/`, run from the repository root with `python -m`. They are **standalone**: they need only
the standard library, `opencv-python` and `numpy`, never DFU's `core` (so they also work on a PC without the rest
installed). Same ports as DFU (answers on UDP 9000, video on 11111), so the same firewall rules apply.

## set_tello_wifi: Tello on your network (station mode)

```bash
python -m tools.set_tello_wifi --ssid LAB_WIFI --password secret123
python -m tools.set_tello_wifi --ssid LAB_WIFI --password secret123 --ip 192.168.10.133   # Tello already on a network
```

1. PC on the Tello's hotspot `TELLO-xxxxxx` (or on the network the Tello is on, plus `--ip`).
2. Run it. The Tello answers, reboots and joins the network.
3. Find its new IP in the router's DHCP list, put it in `config/mydrone.json`, and put the PC on that network.

Only **Tello EDU / Tello Talent** support this. Password ≥ 8 characters, no spaces. Nothing is stored. Several drones:
[Tello models](tello_models.md#several-tellos-at-once).
Back to hotspot mode: hold the Tello's power button ~5 s until the LED blinks.

## Camera calibration

Needed for undistortion and ArUco distances. A calibration is made **per camera and resolution**.

**Board:** print a chessboard (default 11 x 8 squares = **10 x 7 inner corners**, 25 mm squares) and tape it to
something **stiff**. A bending board is the most common cause of bad results.

```bash
# 1. capture ~30 pictures
python -m tools.calibration capture --camera tello --ip 192.168.10.133
python -m tools.calibration capture --camera webcam --index 0                  # laptop camera -> name "webcam"

# 2. compute + save core/video/calibration/<name>.npz
python -m tools.calibration calibrate --name tello

# 3. check it
python -m tools.calibration verify --camera tello --ip 192.168.10.133
python -m tools.calibration verify --name tello --images tools/calibration/images/tello     # on saved pictures

python -m tools.calibration list             # all calibrations with size, error, focal length
```

### capture

Live video. The board is highlighted green when found. **SPACE** saves (the raw frame), **TAB** detection on/off,
**ESC** quit. Pictures go to `tools/calibration/images/<name>/` (not in git); numbering continues if you run it again.

Good pictures:

- board **big** in the image (fill a third or more) as well as further away
- in **every part** of the image: corners and edges, not only the centre (that's where distortion is)
- **tilted** in different directions (up to ~45°)
- **sharp**: hold still before SPACE; the Tello compresses moving images heavily

### calibrate

| Option | Default | |
|---|---|---|
| `--name` | `tello` / `webcam` (from `--camera`) | output name |
| `--out` | `core/video/calibration` | where the `.npz` goes |
| `--images` | `tools/calibration/images/<name>` | picture folder |
| `--cols`, `--rows` | 10, 7 | **inner** corners |
| `--square` | 25 | square edge in mm |
| `--show` | | show the found corners of each picture |

It prints the camera matrix, distortion, the **RMS reprojection error** and the 3 worst pictures:

| RMS | |
|---|---|
| < 0.5 px | very good |
| < 1 px | fine |
| > 1 px | delete the worst/blurry pictures and run again, or capture new ones |

At least 10 usable pictures are needed. Pictures of another size than the first are skipped with a warning.

### verify

Original and undistorted side by side with a grid. Straight edges in the room (door frames, tables) must be
straight on the right. **A** toggles alpha 1 (all pixels) / 0 (cropped), **ESC** quits.

### Use it

```toml
[video]
calibration = "tello"
```

The Tello video is read with OpenCV's FFmpeg backend in a thread that keeps only the newest frame (no lag build-up).

## count1.ps1

Lines of code per folder and file type (Windows PowerShell):

```powershell
powershell -ExecutionPolicy Bypass -File tools/count1.ps1            # summary
powershell -ExecutionPolicy Bypass -File tools/count1.ps1 -Detail    # + every file
```

Skips `.venv`, caches, `logs/` and calibration pictures.
