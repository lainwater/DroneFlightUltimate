"""tools/ - standalone: they must work without importing DFU's core."""

import socket
import subprocess
import sys
import threading
from pathlib import Path

import cv2 as cv
import numpy as np
import pytest

from core.video.calibration import load_calibration
from tools.calibration import calib_io
from tools.calibration.calibrate import calibrate_images, run
from tools.calibration.verify import side_by_side
from tools.set_tello_wifi import set_wifi

ROOT = Path(__file__).resolve().parents[2]


def test_tools_do_not_import_core():
    code = (
        "import sys; import tools.set_tello_wifi, tools.calibration.__main__, tools.calibration.capture, "
        "tools.calibration.verify, tools.calibration.calibrate, tools.calibration.camera; "
        "print(any(m == 'core' or m.startswith('core.') for m in sys.modules))"
    )
    out = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    assert out == "False"


def _chessboard_views(K, n=14, size=(960, 720), cols=10, rows=7, square=0.025):
    """Pictures of a (cols+1) x (rows+1) chessboard from known poses, mild lens distortion."""
    cell = 40
    board = np.zeros(((rows + 1) * cell, (cols + 1) * cell), np.uint8)
    for r in range(rows + 1):
        for c in range(cols + 1):
            if (r + c) % 2 == 0:
                board[r * cell : (r + 1) * cell, c * cell : (c + 1) * cell] = 255
    board = cv.copyMakeBorder(board, cell, cell, cell, cell, cv.BORDER_CONSTANT, value=255)
    h, w = board.shape
    obj = np.float32([[0, 0, 0], [w, 0, 0], [w, h, 0], [0, h, 0]]) * (square / cell) - np.float32([w, h, 0]) * (square / cell) / 2
    rng = np.random.default_rng(1)
    pics = []
    for _ in range(n):
        rvec = np.array([np.pi + rng.uniform(-0.5, 0.5), rng.uniform(-0.5, 0.5), rng.uniform(-0.3, 0.3)])
        tvec = np.array([rng.uniform(-0.08, 0.08), rng.uniform(-0.06, 0.06), rng.uniform(0.35, 0.55)])
        dst, _ = cv.projectPoints(obj, rvec, tvec, K, None)
        H = cv.getPerspectiveTransform(np.float32([[0, 0], [w, 0], [w, h], [0, h]]), dst.reshape(4, 2).astype(np.float32))
        pics.append(cv.cvtColor(cv.warpPerspective(board, H, size, borderValue=120), cv.COLOR_GRAY2BGR))
    return pics


def test_calibrate_recovers_the_camera(tmp_path):
    K = np.array([[900.0, 0, 480], [0, 900, 360], [0, 0, 1]])
    for i, pic in enumerate(_chessboard_views(K)):
        cv.imwrite(str(tmp_path / f"img_{i:03d}.png"), pic)
    path = run(tmp_path, "synthetic", 10, 7, 25.0, show=False, out_dir=tmp_path / "out")
    calib = load_calibration(path)  # the format DFU reads
    assert calib.image_size == (960, 720) and calib.rms < 1.0
    assert calib.camera_matrix[0, 0] == pytest.approx(900, rel=0.03)
    assert calib.camera_matrix[0, 2] == pytest.approx(480, abs=25)


def test_calibrate_needs_enough_pictures(tmp_path):
    pics = _chessboard_views(np.array([[900.0, 0, 480], [0, 900, 360], [0, 0, 1]]), n=3)
    files = []
    for i, pic in enumerate(pics):
        files.append(tmp_path / f"{i}.png")
        cv.imwrite(str(files[-1]), pic)
    with pytest.raises(RuntimeError, match="at least"):
        calibrate_images(files, 10, 7, 25.0, log=lambda *_: None)


def test_calib_io_matches_core_format(tmp_path):
    K = np.array([[500.0, 0, 320], [0, 500, 240], [0, 0, 1]])
    path = calib_io.save("cam", K, np.zeros(5), (640, 480), 0.4, tmp_path)
    core = load_calibration(path)
    tool = calib_io.load("cam", tmp_path)
    assert np.allclose(core.camera_matrix, tool["camera_matrix"]) and core.image_size == tool["image_size"] == (640, 480)


def test_verify_view():
    calib = calib_io.load("tello")
    view = side_by_side(np.zeros((720, 960, 3), np.uint8), calib_io.Undistorter(calib))
    assert view.shape == (720, 1920, 3)
    with pytest.raises(RuntimeError, match="960x720"):
        calib_io.check_size(calib, np.zeros((240, 320, 3)))


def _fake_tello(answers):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", 0))
    got = []

    def loop():
        for answer in answers:
            data, addr = sock.recvfrom(1024)
            got.append(data.decode())
            if answer is not None:
                sock.sendto(answer.encode(), addr)

    threading.Thread(target=loop, daemon=True).start()
    return sock, got


def test_set_wifi(monkeypatch):
    sock, got = _fake_tello(["ok", "ok"])
    monkeypatch.setattr("tools.set_tello_wifi.TELLO_PORT", sock.getsockname()[1])
    assert set_wifi("127.0.0.1", "LAB", "secret123", local_port=0, timeout=2)
    assert got == ["command", "ap LAB secret123"]
    sock.close()


def test_set_wifi_basic_tello_refuses(monkeypatch):
    sock, got = _fake_tello(["ok", "error"])
    monkeypatch.setattr("tools.set_tello_wifi.TELLO_PORT", sock.getsockname()[1])
    assert not set_wifi("127.0.0.1", "LAB", "secret123", local_port=0, timeout=2)
    sock.close()


def test_set_wifi_no_tello(monkeypatch):
    sock, _ = _fake_tello([None])
    monkeypatch.setattr("tools.set_tello_wifi.TELLO_PORT", sock.getsockname()[1])
    assert not set_wifi("127.0.0.1", "LAB", "secret123", local_port=0, timeout=0.3)
    sock.close()


def test_count_script_exists():
    assert "Get-ChildItem" in (ROOT / "tools" / "count1.ps1").read_text()
