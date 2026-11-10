"""
Camera-geometry helpers for CV2Display: undistortion and ArUco markers.

Both need a camera calibration (core/video/calibration). Everything here is
plain blocking OpenCV - CV2Display calls the slow parts via asyncio.to_thread.

Coordinate frame of a marker pose = OpenCV camera frame:
    x right, y down, z forward (out of the lens), metres.
"""

import math

import cv2 as cv
import numpy as np

from core.video.calibration import CameraCalibration

ARUCO_DICTIONARIES = sorted(name for name in dir(cv.aruco) if name.startswith("DICT_"))


class Undistorter:
    """Undistort frames of ONE calibrated camera. The remap tables are computed
    once (first frame) and reused - remap itself is cheap (~2 ms at 960x720).

    alpha 1.0 = keep every pixel (curved black borders),
    alpha 0.0 = crop to the area without borders."""

    def __init__(self, calibration: CameraCalibration, alpha: float = 1.0):
        self.calibration = calibration
        self.alpha = float(alpha)
        self.new_camera_matrix: np.ndarray | None = None
        self._maps = None
        self._size: tuple[int, int] | None = None

    def apply(self, frame: np.ndarray) -> np.ndarray:
        h, w = frame.shape[:2]
        if self._size != (w, h):
            K, dist = self.calibration.camera_matrix, self.calibration.dist_coeffs
            self.new_camera_matrix, _ = cv.getOptimalNewCameraMatrix(K, dist, (w, h), self.alpha, (w, h))
            self._maps = cv.initUndistortRectifyMap(K, dist, None, self.new_camera_matrix, (w, h), cv.CV_16SC2)
            self._size = (w, h)
        return cv.remap(frame, self._maps[0], self._maps[1], interpolation=cv.INTER_LINEAR)


def rotation_matrix_to_euler_xyz(R: np.ndarray) -> tuple[float, float, float]:
    """3x3 rotation -> roll, pitch, yaw in degrees.
    Same as scipy Rotation.from_matrix(R).as_euler("xyz", degrees=True)."""
    roll = math.atan2(R[2, 1], R[2, 2])
    pitch = math.asin(max(-1.0, min(1.0, -R[2, 0])))
    yaw = math.atan2(R[1, 0], R[0, 0])
    return math.degrees(roll), math.degrees(pitch), math.degrees(yaw)


class ArucoMarkerDetector:
    """Detect ArUco markers and, with camera parameters, localize them.

    dictionary  - e.g. "DICT_5X5_50" (must match the printed markers)
    marker_size - edge length of the BLACK square in metres (pose scale!)
    """

    def __init__(self, dictionary: str = "DICT_5X5_50", marker_size: float = 0.15):
        if dictionary not in ARUCO_DICTIONARIES:
            raise ValueError(f"Unknown ArUco dictionary {dictionary!r}. Examples: DICT_4X4_50, DICT_5X5_50, DICT_6X6_250")
        self.dictionary_name = dictionary
        self.marker_size = float(marker_size)
        self._dictionary = cv.aruco.getPredefinedDictionary(getattr(cv.aruco, dictionary))
        if hasattr(cv.aruco, "ArucoDetector"):  # OpenCV >= 4.7
            self._detector = cv.aruco.ArucoDetector(self._dictionary, cv.aruco.DetectorParameters())
        else:  # older OpenCV
            self._detector = None
        s = self.marker_size / 2
        # corner order returned by the detector: top-left, top-right, bottom-right, bottom-left
        self._object_points = np.array([[-s, s, 0], [s, s, 0], [s, -s, 0], [-s, -s, 0]], dtype=np.float32)

    def _detect_raw(self, gray):
        if self._detector is not None:
            return self._detector.detectMarkers(gray)
        return cv.aruco.detectMarkers(gray, self._dictionary)

    def detect(self, frame: np.ndarray, camera_matrix: np.ndarray | None = None, dist_coeffs: np.ndarray | None = None) -> list[dict]:
        """Blocking. Returns one dict per marker:
        id, center (px), corners (4x[x,y] px)
        + with camera parameters: x, y, z, distance (m), roll, pitch, yaw (deg),
          rvec, tvec, axes (px: origin, x-, y-, z-axis end, for drawing)
        """
        gray = cv.cvtColor(frame, cv.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
        corners, ids, _ = self._detect_raw(gray)
        if ids is None:
            return []
        markers = []
        for marker_id, corner in zip(ids.flatten(), corners):
            image_points = corner.reshape(4, 2).astype(np.float32)
            marker = {
                "id": int(marker_id),
                "center": [float(v) for v in image_points.mean(axis=0)],
                "corners": image_points.tolist(),
            }
            if camera_matrix is not None:
                marker.update(self._pose(image_points, camera_matrix, dist_coeffs))
            markers.append(marker)
        return markers

    def _pose(self, image_points, K, dist) -> dict:
        if dist is None:
            dist = np.zeros((1, 5))
        ok, rvec, tvec = cv.solvePnP(self._object_points, image_points, K, dist, flags=cv.SOLVEPNP_IPPE_SQUARE)
        if not ok:
            return {}
        R, _ = cv.Rodrigues(rvec)
        roll, pitch, yaw = rotation_matrix_to_euler_xyz(R)
        x, y, z = (float(v) for v in tvec.flatten())
        axis_len = self.marker_size / 2
        axis_3d = np.float32([[0, 0, 0], [axis_len, 0, 0], [0, axis_len, 0], [0, 0, axis_len]])
        axes, _ = cv.projectPoints(axis_3d, rvec, tvec, K, dist)
        return {
            "x": x,
            "y": y,
            "z": z,
            "distance": math.sqrt(x * x + y * y + z * z),
            "roll": roll,
            "pitch": pitch,
            "yaw": yaw,
            "rvec": [float(v) for v in rvec.flatten()],
            "tvec": [x, y, z],
            "axes": axes.reshape(4, 2).tolist(),
        }
