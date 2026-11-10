"""calibrate - chessboard pictures -> core/video/calibration/<name>.npz"""

from dataclasses import dataclass
from pathlib import Path

import cv2 as cv
import numpy as np

from tools.calibration.calib_io import DEFAULT_OUT_DIR, save

MIN_IMAGES = 10  # fewer gives unstable distortion values


@dataclass
class CalibrationResult:
    camera_matrix: np.ndarray
    dist_coeffs: np.ndarray
    image_size: tuple[int, int]
    rms: float
    used: list[Path]
    per_image_error: list[float]


def calibrate_images(files: list[Path], cols: int, rows: int, square_mm: float, show: bool = False, log=print) -> CalibrationResult:
    objp = np.zeros((rows * cols, 3), np.float32)
    objp[:, :2] = np.mgrid[0:cols, 0:rows].T.reshape(-1, 2)
    objp *= square_mm

    obj_points, img_points, used = [], [], []
    image_size = None
    criteria = (cv.TERM_CRITERIA_EPS + cv.TERM_CRITERIA_MAX_ITER, 30, 0.001)
    for path in files:
        img = cv.imread(str(path))
        if img is None:
            log(f"[SKIP]   {path.name}: not an image")
            continue
        size = (img.shape[1], img.shape[0])
        if image_size is None:
            image_size = size
        elif size != image_size:
            log(f"[SKIP]   {path.name}: {size[0]}x{size[1]}, the others are {image_size[0]}x{image_size[1]} (different camera/resolution?)")
            continue
        gray = cv.cvtColor(img, cv.COLOR_BGR2GRAY)
        found, corners = cv.findChessboardCorners(gray, (cols, rows), cv.CALIB_CB_ADAPTIVE_THRESH + cv.CALIB_CB_NORMALIZE_IMAGE)
        if not found:
            log(f"[NO BOARD] {path.name}")
            continue
        corners = cv.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
        obj_points.append(objp)
        img_points.append(corners)
        used.append(path)
        log(f"[OK]     {path.name}")
        if show:
            vis = img.copy()
            cv.drawChessboardCorners(vis, (cols, rows), corners, found)
            cv.imshow("Corners", vis)
            cv.waitKey(200)
    if show:
        cv.destroyWindow("Corners")

    if len(used) < MIN_IMAGES:
        raise RuntimeError(f"Only {len(used)} usable pictures, need at least {MIN_IMAGES}. Capture more (and check --cols/--rows).")

    rms, K, dist, rvecs, tvecs = cv.calibrateCamera(obj_points, img_points, image_size, None, None)
    errors = []
    for objp_i, imgp_i, rvec, tvec in zip(obj_points, img_points, rvecs, tvecs):
        projected, _ = cv.projectPoints(objp_i, rvec, tvec, K, dist)
        errors.append(float(np.sqrt(np.mean(np.sum((imgp_i.reshape(-1, 2) - projected.reshape(-1, 2)) ** 2, axis=1)))))
    return CalibrationResult(K, dist, image_size, float(rms), used, errors)


def run(folder: Path, name: str, cols: int, rows: int, square_mm: float, show: bool, out_dir: Path = DEFAULT_OUT_DIR) -> Path:
    files = sorted(p for p in folder.glob("*") if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".bmp"))
    print(f"{len(files)} pictures in {folder}  (board {cols}x{rows} inner corners, squares {square_mm} mm)")
    if not files:
        raise RuntimeError(f"No pictures in {folder} - run 'capture' first (or pass --images).")
    result = calibrate_images(files, cols, rows, square_mm, show)

    np.set_printoptions(precision=4, suppress=True)
    print(f"\nused {len(result.used)} of {len(files)} pictures, {result.image_size[0]}x{result.image_size[1]}")
    print("\ncamera matrix K:\n", result.camera_matrix)
    print("\ndistortion (k1 k2 p1 p2 k3):\n", result.dist_coeffs.ravel())
    print(f"\nRMS reprojection error: {result.rms:.3f} px   (< 0.5 very good, < 1 fine, > 1 check your pictures)")
    worst = sorted(zip(result.per_image_error, result.used), reverse=True)[:3]
    print("worst pictures: " + ", ".join(f"{p.name} {e:.2f} px" for e, p in worst) + "  (delete blurry ones and run again)")

    path = save(name, result.camera_matrix, result.dist_coeffs, result.image_size, result.rms, out_dir)
    print(f"\nSaved {path}\nUse it: get_videostream(..., calibration='{name}')  or  [video] calibration = \"{name}\" in defaults.toml")
    return path
