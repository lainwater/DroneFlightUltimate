"""Calibration files and ArUco localization (no window needed)."""

import cv2 as cv
import numpy as np
import pytest

from core.video.calibration import available_calibrations, load_calibration, save_calibration
from core.video.implementations.cv2.vision import ArucoMarkerDetector, Undistorter, rotation_matrix_to_euler_xyz


def test_shipped_calibrations_load_with_size():
    assert {"tello", "webcam"} <= set(available_calibrations())
    tello = load_calibration("tello")
    assert tello.image_size == (960, 720)
    assert tello.camera_matrix.shape == (3, 3) and tello.dist_coeffs.shape[0] == 1
    assert tello.matches((720, 960, 3)) and not tello.matches((240, 320, 3))


def test_save_and_load_roundtrip(tmp_path):
    K = np.array([[500.0, 0, 320], [0, 500, 240], [0, 0, 1]])
    path = save_calibration("cam", K, np.zeros(5), (640, 480), rms=0.3, folder=tmp_path)
    c = load_calibration(path)
    assert np.allclose(c.camera_matrix, K) and c.image_size == (640, 480) and c.rms == pytest.approx(0.3)


def test_missing_calibration_lists_available():
    with pytest.raises(FileNotFoundError, match="tello"):
        load_calibration("does_not_exist")


def _rotation(roll, pitch, yaw):
    r, p, y = np.radians([roll, pitch, yaw])
    Rx = np.array([[1, 0, 0], [0, np.cos(r), -np.sin(r)], [0, np.sin(r), np.cos(r)]])
    Ry = np.array([[np.cos(p), 0, np.sin(p)], [0, 1, 0], [-np.sin(p), 0, np.cos(p)]])
    Rz = np.array([[np.cos(y), -np.sin(y), 0], [np.sin(y), np.cos(y), 0], [0, 0, 1]])
    return Rz @ Ry @ Rx  # extrinsic xyz


def test_euler_roundtrip():
    for angles in [(10, 20, 30), (-170, 5, 90), (165, -40, -120)]:
        assert np.allclose(rotation_matrix_to_euler_xyz(_rotation(*angles)), angles, atol=1e-6)


def _scene(K, t, rpy, edge=0.15, size=(960, 720)):
    """Marker id 7 rendered at a known pose (no lens distortion)."""
    d = cv.aruco.getPredefinedDictionary(cv.aruco.DICT_5X5_50)
    img = cv.copyMakeBorder(cv.aruco.generateImageMarker(d, 7, 400), 100, 100, 100, 100, cv.BORDER_CONSTANT, value=255)
    s = edge / 2
    obj = np.float32([[-s, s, 0], [s, s, 0], [s, -s, 0], [-s, -s, 0]])
    rvec, _ = cv.Rodrigues(_rotation(*rpy))
    dst, _ = cv.projectPoints(obj, rvec, np.array(t, float), K, None)
    H = cv.getPerspectiveTransform(np.float32([[100, 100], [500, 100], [500, 500], [100, 500]]), dst.reshape(4, 2).astype(np.float32))
    return cv.cvtColor(cv.warpPerspective(img, H, size, borderValue=170), cv.COLOR_GRAY2BGR)


@pytest.mark.parametrize("t, rpy", [((0.1, -0.05, 1.2), (170, 20, 30)), ((0.0, 0.0, 0.6), (-160, 5, 90))])
def test_aruco_pose(t, rpy):
    K = load_calibration("tello").camera_matrix
    markers = ArucoMarkerDetector("DICT_5X5_50", 0.15).detect(_scene(K, t, rpy), K, np.zeros((1, 5)))
    assert [m["id"] for m in markers] == [7]
    m = markers[0]
    assert np.allclose(m["tvec"], t, atol=0.02)
    assert np.allclose((m["roll"], m["pitch"], m["yaw"]), rpy, atol=2)


def test_aruco_without_calibration_has_no_pose():
    K = load_calibration("tello").camera_matrix
    (m,) = ArucoMarkerDetector().detect(_scene(K, (0, 0, 1.0), (180, 0, 0)))
    assert m["id"] == 7 and "distance" not in m


def test_undistort_keeps_size():
    frame = np.zeros((720, 960, 3), np.uint8)
    assert Undistorter(load_calibration("tello"), 0.0).apply(frame).shape == frame.shape


def test_unknown_dictionary():
    with pytest.raises(ValueError):
        ArucoMarkerDetector("DICT_NOPE")
