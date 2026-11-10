"""CV2Display without a screen: the window functions are replaced, frames come over the bus."""

import asyncio

import cv2 as cv
import numpy as np
import pytest

from core.bus import get_bus
from core.video import VideoOutputType, get_videostream
from core.video.calibration import load_calibration


@pytest.fixture
def headless(monkeypatch):
    shown = {}
    monkeypatch.setattr(cv, "namedWindow", lambda *a, **k: None)
    monkeypatch.setattr(cv, "destroyWindow", lambda *a, **k: None)
    monkeypatch.setattr(cv, "waitKey", lambda *a, **k: -1)
    monkeypatch.setattr(cv, "imshow", lambda name, frame: shown.__setitem__(name, frame.copy()))
    return shown


def _marker_scene(K, t=(0.0, 0.0, 1.0), size=(960, 720)):
    """Marker id 7 (DICT_5X5_50, 15 cm) facing the camera at distance t[2]."""
    d = cv.aruco.getPredefinedDictionary(cv.aruco.DICT_5X5_50)
    img = cv.copyMakeBorder(cv.aruco.generateImageMarker(d, 7, 400), 100, 100, 100, 100, cv.BORDER_CONSTANT, value=255)
    s = 0.075
    obj = np.float32([[-s, s, 0], [s, s, 0], [s, -s, 0], [-s, -s, 0]])
    rvec = np.array([np.pi, 0, 0])  # facing the camera
    dst, _ = cv.projectPoints(obj, rvec, np.array(t, float), K, None)
    H = cv.getPerspectiveTransform(np.float32([[100, 100], [500, 100], [500, 500], [100, 500]]), dst.reshape(4, 2).astype(np.float32))
    return cv.cvtColor(cv.warpPerspective(img, H, size, borderValue=170), cv.COLOR_GRAY2BGR)


async def _session(frames, setup, tmp_path, **kwargs):
    bus = get_bus()
    events = []
    bus.subscribe("*", lambda t, d: events.append((t, d)) if not t.startswith("frame") else None)
    video = get_videostream(VideoOutputType.CV2, "d", bus, media_dir=tmp_path, **kwargs)
    await video.start_stream()
    await setup(video, bus)
    for frame in frames:
        await bus.publish("frame.d", {"ts": 0, "seq": 0, "encoding": "bgr24", "frame": frame})
        await asyncio.sleep(0.03)
    await asyncio.sleep(0.1)
    await bus.publish("frame.d", {"frame": frames[-1]})  # draw the last results
    result = (video, events)
    await video.stop_stream()
    return result


def test_shows_frames_with_overlays(headless, tmp_path):
    async def setup(video, bus):
        await bus.publish("state.d", {"battery": 87, "height": 80, "attitude": {"pitch": 0, "roll": 1, "yaw": 90}})
        await video.turn_on_display_state_data(("battery", "height", "attitude"))
        await bus.publish("display.d", {"dist": 1.234, "R": np.eye(2)})

    video, _ = asyncio.run(_session([np.zeros((720, 960, 3), np.uint8)] * 3, setup, tmp_path))
    assert headless["d"].shape == (720, 960, 3)
    assert video.custom_data["dist"] == 1.234
    assert video._format_value({"pitch": 0, "roll": 1.0, "yaw": 90}) == "pitch 0, roll 1, yaw 90"
    assert video._custom_data_lines() == ["dist: 1.23", "R: [ 1  0 ]", "   [ 0  1 ]"]


def test_small_frames_are_enlarged(headless, tmp_path):
    asyncio.run(_session([np.zeros((240, 320, 3), np.uint8)], lambda v, b: asyncio.sleep(0), tmp_path))
    assert headless["d"].shape == (720, 960, 3)


def test_aruco_pose_and_publish(headless, tmp_path):
    K = load_calibration("tello").camera_matrix
    frames = [_marker_scene(K)] * 6

    async def setup(video, bus):
        await video.start_aruco(publish=True)

    video, events = asyncio.run(_session(frames, setup, tmp_path, calibration="tello"))
    published = [d["aruco"] for t, d in events if t == "data.stream.d" and "aruco" in d]
    assert published and published[-1][0]["id"] == 7
    assert published[-1][0]["z"] == pytest.approx(1.0, abs=0.05)  # real lens distortion is not in the scene: ~ within 5 cm


def test_aruco_without_calibration_detects_only(headless, tmp_path):
    K = load_calibration("tello").camera_matrix

    async def setup(video, bus):
        await video.start_aruco(publish=True)

    _, events = asyncio.run(_session([_marker_scene(K)] * 4, setup, tmp_path))
    assert any(t == "error.stream.d" and "No camera calibration" in d["message"] for t, d in events)
    markers = [d["aruco"] for t, d in events if t == "data.stream.d"][-1]
    assert markers[0]["id"] == 7 and "z" not in markers[0]


def test_undistort_pauses_on_other_resolution(headless, tmp_path):
    async def setup(video, bus):
        await video.undistort_on()

    video, _ = asyncio.run(_session([np.zeros((240, 320, 3), np.uint8)] * 2, setup, tmp_path, calibration="tello"))
    assert "960x720" in video._undistort_note


def test_snapshot_and_recording(headless, tmp_path):
    async def setup(video, bus):
        await bus.publish("frame.d", {"frame": np.zeros((720, 960, 3), np.uint8)})
        await video.take_snapshot()
        await video.start_recording()

    video, events = asyncio.run(_session([np.zeros((720, 960, 3), np.uint8)] * 3, setup, tmp_path))
    asyncio.run(video.stop_recording())
    assert len(list(tmp_path.glob("*.jpg"))) == 1 and len(list(tmp_path.glob("*.mp4"))) == 1


def test_unknown_command(headless, tmp_path):
    async def setup(video, bus):
        await bus.publish("cmd.stream.d", {"action": "fly_to_the_moon"})

    _, events = asyncio.run(_session([np.zeros((720, 960, 3), np.uint8)], setup, tmp_path))
    assert any(t == "error.stream.d" and d["error"] == "NotCapable" for t, d in events)
