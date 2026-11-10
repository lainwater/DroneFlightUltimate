"""
calib_io - read/write calibration files and undistort. Standalone (cv2 + numpy).

Same .npz format DFU reads (core/video/calibration):
    camera_matrix (3x3), distortion_coefficients (1x5), image_size (w, h), rms (px)
"""

from pathlib import Path

import cv2 as cv
import numpy as np

# repo/core/video/calibration - where DFU looks for calibrations
DEFAULT_OUT_DIR = Path(__file__).resolve().parents[2] / "core" / "video" / "calibration"


def save(name: str, camera_matrix, dist_coeffs, image_size: tuple[int, int], rms: float | None = None, folder: Path = DEFAULT_OUT_DIR) -> Path:
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{name}.npz"
    extra = {} if rms is None else {"rms": float(rms)}
    np.savez(
        path,
        camera_matrix=np.asarray(camera_matrix, dtype=np.float64),
        distortion_coefficients=np.asarray(dist_coeffs, dtype=np.float64).reshape(1, -1),
        image_size=np.array(image_size, dtype=np.int32),
        **extra,
    )
    return path


def path_for(name_or_path: str | Path, folder: Path = DEFAULT_OUT_DIR) -> Path:
    p = Path(name_or_path)
    return p if p.suffix == ".npz" and p.exists() else Path(folder) / f"{p.stem}.npz"


def load(name_or_path: str | Path, folder: Path = DEFAULT_OUT_DIR) -> dict:
    """-> {"name", "camera_matrix", "dist_coeffs", "image_size" or None, "rms" or None}"""
    path = path_for(name_or_path, folder)
    if not path.exists():
        names = ", ".join(sorted(p.stem for p in Path(folder).glob("*.npz"))) or "none"
        raise FileNotFoundError(f"No calibration '{name_or_path}' ({path}). Available: {names}")
    with np.load(path) as d:
        return {
            "name": path.stem,
            "camera_matrix": np.asarray(d["camera_matrix"], dtype=np.float64),
            "dist_coeffs": np.asarray(d["distortion_coefficients"], dtype=np.float64).reshape(1, -1),
            "image_size": tuple(int(v) for v in d["image_size"]) if "image_size" in d.files else None,
            "rms": float(d["rms"]) if "rms" in d.files else None,
        }


def list_all(folder: Path = DEFAULT_OUT_DIR) -> list[dict]:
    return [load(p) for p in sorted(Path(folder).glob("*.npz"))]


class Undistorter:
    """Remap tables computed once per image size. alpha 1 = all pixels, 0 = cropped."""

    def __init__(self, calib: dict, alpha: float = 1.0):
        self.calib = calib
        self.alpha = float(alpha)
        self._size = None
        self._maps = None

    def apply(self, frame):
        h, w = frame.shape[:2]
        if self._size != (w, h):
            K, dist = self.calib["camera_matrix"], self.calib["dist_coeffs"]
            new_K, _ = cv.getOptimalNewCameraMatrix(K, dist, (w, h), self.alpha, (w, h))
            self._maps = cv.initUndistortRectifyMap(K, dist, None, new_K, (w, h), cv.CV_16SC2)
            self._size = (w, h)
        return cv.remap(frame, self._maps[0], self._maps[1], interpolation=cv.INTER_LINEAR)


def check_size(calib: dict, frame) -> None:
    size = calib.get("image_size")
    if size and (frame.shape[1], frame.shape[0]) != tuple(size):
        raise RuntimeError(f"calibration '{calib['name']}' is for {size[0]}x{size[1]}, the frame is {frame.shape[1]}x{frame.shape[0]}")
