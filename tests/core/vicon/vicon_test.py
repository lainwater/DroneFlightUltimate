"""core.vicon with a fake vicon_dssdk (the real one only exists on the lab PC)."""

import asyncio
import math
import sys
import time
import types

import pytest

from core.bus import get_bus
from core.vicon import get_vicon, quat_to_euler_xyz


def _fake_sdk(monkeypatch, occluded=False, fail_connect=False, frame_s=0.002):
    class Client:
        class StreamMode:
            EClientPull = 0

        def SetStreamMode(self, mode):
            pass

        def SetBufferSize(self, n):
            pass

        def Connect(self, host):
            self.ok = not fail_connect

        def IsConnected(self):
            return self.ok

        def EnableSegmentData(self):
            pass

        def GetFrame(self):
            time.sleep(frame_s)

        def GetSegmentGlobalTranslation(self, subject, segment):
            if subject != "tello-1":
                raise RuntimeError("InvalidSubjectName")
            return (time.time() * 1000, 2.0, 3.0), occluded  # x = now in ms, to measure lag

        def GetSegmentGlobalRotationQuaternion(self, subject, segment):
            return (0.0, 0.0, math.sin(math.pi / 8), math.cos(math.pi / 8)), occluded  # yaw 45 deg

        def Disconnect(self):
            pass

    module = types.ModuleType("vicon_dssdk")
    module.ViconDataStream = types.SimpleNamespace(Client=Client)
    monkeypatch.setitem(sys.modules, "vicon_dssdk", module)
    monkeypatch.setitem(sys.modules, "vicon_dssdk.ViconDataStream", module.ViconDataStream)


async def _run(seconds, slow_handler=0.0, **kwargs):
    bus = get_bus()
    got = []

    def handler(topic, data):
        got.append((topic, data, time.time()))
        time.sleep(slow_handler)  # a busy event loop

    bus.subscribe("*", handler)
    vicon = get_vicon("d", bus, rate_hz=20, **kwargs)
    await vicon.start()
    await asyncio.sleep(seconds)
    await vicon.stop()
    await asyncio.sleep(0.05)
    return got, vicon


def test_publishes_pose(monkeypatch):
    _fake_sdk(monkeypatch)
    got, vicon = asyncio.run(_run(0.5))
    poses = [d for t, d, _ in got if t == "vicon.d"]
    assert 5 <= len(poses) <= 15  # ~20 Hz
    p = poses[-1]
    assert p["subject"] == "tello-1" and not p["occluded"] and p["yaw"] == pytest.approx(45)
    assert ("ack.vicon.d", "connect") in [(t, d.get("cmd")) for t, d, _ in got]
    assert vicon.latest["yaw"] == pytest.approx(45)


def test_never_falls_behind_a_busy_loop(monkeypatch):
    _fake_sdk(monkeypatch)
    got, _ = asyncio.run(_run(1.5, slow_handler=0.15))
    lags = [received - d["x"] / 1000 for t, d, received in got if t == "vicon.d"]
    assert max(lags) < 0.4  # latest-only: old samples are dropped, not queued


def test_occluded(monkeypatch):
    _fake_sdk(monkeypatch, occluded=True)
    got, _ = asyncio.run(_run(0.3))
    p = [d for t, d, _ in got if t == "vicon.d"][-1]
    assert p["occluded"] and "x" not in p


def test_connect_failure_and_wrong_subject(monkeypatch):
    _fake_sdk(monkeypatch, fail_connect=True)
    got, _ = asyncio.run(_run(0.2))
    assert any(t == "error.vicon.d" and d["error"] == "ConnectFailed" for t, d, _ in got)
    _fake_sdk(monkeypatch)
    got, _ = asyncio.run(_run(0.3, subject="nope"))
    errors = [d for t, d, _ in got if t == "error.vicon.d"]
    assert len(errors) == 1 and "InvalidSubjectName" in errors[0]["message"]  # reported once, not every frame


def test_missing_sdk(monkeypatch):
    monkeypatch.setitem(sys.modules, "vicon_dssdk", None)
    got, _ = asyncio.run(_run(0.1))
    assert any(t == "error.vicon.d" and d["error"] == "ModuleNotFoundError" for t, d, _ in got)


def test_quaternion_to_euler():
    assert quat_to_euler_xyz(0, 0, 0, 1) == (0, 0, 0)
    roll, pitch, yaw = quat_to_euler_xyz(0, 0, math.sin(math.pi / 4), math.cos(math.pi / 4))
    assert yaw == pytest.approx(90) and roll == pytest.approx(0)
