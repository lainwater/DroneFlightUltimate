"""
Camera calibration with a printed chessboard. Standalone: needs only opencv-python
and numpy (no DFU). Run from the repo root:

    python -m tools.calibration capture   --camera tello --ip 192.168.10.133
    python -m tools.calibration capture   --camera webcam --index 0
    python -m tools.calibration calibrate --name tello
    python -m tools.calibration verify    --camera tello --ip 192.168.10.133
    python -m tools.calibration list

1. capture   - live video, the chessboard is highlighted when found.
               SPACE saves a picture to tools/calibration/images/<name>/.
               Take 20-40 pictures: board close and far, in every corner of
               the image, tilted in different directions. Keep it sharp
               (motion blur ruins a calibration).
2. calibrate - finds the board in every saved picture, computes the camera
               matrix + distortion and writes core/video/calibration/<name>.npz,
               which CV2Display uses (undistort + ArUco pose).
               RMS reprojection error: < 0.5 px very good, < 1 px fine.
3. verify    - original and undistorted side by side with a grid: straight
               edges in the room must look straight on the right.

Board: COLS x ROWS = INNER corners (a board with 11 x 8 squares has 10 x 7).
The square size only scales distances, it does not change the calibration -
but give the real value anyway (mm) for a correct reprojection check.

A calibration belongs to ONE camera at ONE resolution: Tello forward camera =
"tello" (960x720), laptop camera for the simdrone = "webcam". The Tello video is read
with OpenCV's FFmpeg backend (opencv-python has it), like DFU's own video needs PyAV.
"""

from pathlib import Path

IMAGES_DIR = Path(__file__).parent / "images"
DEFAULT_COLS = 10
DEFAULT_ROWS = 7
DEFAULT_SQUARE_MM = 25.0


def images_dir(name: str) -> Path:
    return IMAGES_DIR / name
