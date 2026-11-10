"""
Camera calibrations - one .npz per camera, stored in this folder.

    from core.video.calibration import load_calibration
    calib = load_calibration("tello")      # -> core/video/calibration/tello.npz
    calib.camera_matrix, calib.dist_coeffs, calib.image_size

Made with tools/calibration (`python -m tools.calibration ...`), which writes
here. File format (np.savez, compatible with the older lab scripts):
    camera_matrix            3x3  (K)
    distortion_coefficients  1x5  (k1, k2, p1, p2, k3)
    image_size               (width, height) the calibration was made at
    rms                      reprojection error in px (optional)

A calibration is only valid for the camera AND resolution it was made with
(the Tello's downward camera is a different camera, even though 320x240 has
the same 4:3 shape). `matches()` tells you whether a frame fits.
"""

from dataclasses import dataclass
from pathlib import Path

import numpy as np

CALIBRATION_DIR = Path(__file__).parent


@dataclass
class CameraCalibration:
    name: str
    camera_matrix: np.ndarray  # K, 3x3
    dist_coeffs: np.ndarray  # 1xN
    image_size: tuple[int, int] | None  # (width, height), None = unknown (old file)
    rms: float | None = None

    def matches(self, frame_shape) -> bool:
        """True if a frame of this shape (h, w[, c]) can use this calibration."""
        if self.image_size is None:
            return True
        return (frame_shape[1], frame_shape[0]) == tuple(self.image_size)

    def mismatch_text(self, frame_shape) -> str:
        w, h = self.image_size
        return f"calibration '{self.name}' is for {w}x{h}, frame is {frame_shape[1]}x{frame_shape[0]}"


def available_calibrations() -> list[str]:
    return sorted(p.stem for p in CALIBRATION_DIR.glob("*.npz"))


def calibration_path(name_or_path: str | Path) -> Path:
    """'tello' -> CALIBRATION_DIR/tello.npz; an existing path is used as is."""
    path = Path(name_or_path)
    if path.suffix == ".npz" and path.exists():
        return path
    return CALIBRATION_DIR / f"{path.stem}.npz"


def load_calibration(name_or_path: str | Path) -> CameraCalibration:
    path = calibration_path(name_or_path)
    if not path.exists():
        raise FileNotFoundError(
            f"No calibration '{name_or_path}' ({path}). Available: {', '.join(available_calibrations()) or 'none'}. "
            "Make one with: python -m tools.calibration --help"
        )
    with np.load(path) as data:
        size = tuple(int(v) for v in data["image_size"]) if "image_size" in data.files else None
        rms = float(data["rms"]) if "rms" in data.files else None
        return CameraCalibration(
            name=path.stem,
            camera_matrix=np.asarray(data["camera_matrix"], dtype=np.float64),
            dist_coeffs=np.asarray(data["distortion_coefficients"], dtype=np.float64).reshape(1, -1),
            image_size=size,
            rms=rms,
        )


def save_calibration(
    name: str, camera_matrix, dist_coeffs, image_size: tuple[int, int], rms: float | None = None, folder: Path = CALIBRATION_DIR
) -> Path:
    """Write <folder>/<name>.npz and return its path."""
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


__all__ = ["CALIBRATION_DIR", "CameraCalibration", "available_calibrations", "calibration_path", "load_calibration", "save_calibration"]
