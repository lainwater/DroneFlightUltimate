"""
ViconReceiver - reads one subject (rigid body) from a Vicon DataStream server
and publishes its pose on the bus.

Needs the Vicon DataStream SDK python wrapper (`vicon_dssdk`). It is NOT on
PyPI - install it from the SDK folder, e.g.
    pip install "C:\\Program Files\\Vicon\\DataStream SDK\\Win64\\Python\\vicon_dssdk"

The SDK calls are blocking (GetFrame waits for the next Vicon frame), so they
run in their own thread - the asyncio event loop (drone, video, keyboard) is
never blocked. Results are handed to the loop with run_coroutine_threadsafe.

Bus contract (drone_id = the drone this subject belongs to):
    vicon.{drone_id}        - {"ts", "frame", "subject", "occluded",
                               "x", "y", "z"            (mm, Vicon world frame),
                               "roll", "pitch", "yaw"   (deg, extrinsic xyz),
                               "qx", "qy", "qz", "qw"}
                              when occluded only ts/frame/subject/occluded are sent.
    ack.vicon.{drone_id}    - {"cmd": "connect"/"disconnect", "ack": "True", "host": ...}
    error.vicon.{drone_id}  - {"error": ..., "message": ...}

Publishing is throttled to `rate_hz` (Vicon itself runs at 100+ Hz) so the
bus, logger and recorder are not flooded. `latest` always holds the newest
pose, independent of the throttle.

Latest-only (LIFO, old samples dropped) - nothing can pile up:
  - Vicon side: ClientPull stream mode + buffer size 1, so GetFrame() always
    returns the NEWEST frame from the server, never a buffered old one.
  - Bus side: at most ONE vicon publish is in flight on the event loop. While
    the loop is busy (video, YOLO), new samples only overwrite `latest`; the
    next publish then sends whatever is newest at that moment.
"""

import asyncio
import math
import threading
import time
from typing import Any


def quat_to_euler_xyz(qx: float, qy: float, qz: float, qw: float) -> tuple[float, float, float]:
    """Quaternion (x, y, z, w) -> roll, pitch, yaw in degrees.
    Same result as scipy Rotation.from_quat([qx, qy, qz, qw]).as_euler("xyz", degrees=True)."""
    roll = math.atan2(2 * (qw * qx + qy * qz), 1 - 2 * (qx * qx + qy * qy))
    pitch = math.asin(max(-1.0, min(1.0, 2 * (qw * qy - qz * qx))))
    yaw = math.atan2(2 * (qw * qz + qx * qy), 1 - 2 * (qy * qy + qz * qz))
    return math.degrees(roll), math.degrees(pitch), math.degrees(yaw)


class ViconReceiver:
    def __init__(
        self,
        drone_id: str,
        bus: object,
        host: str = "192.168.10.1:801",
        subject: str = "tello-1",
        segment: str | None = None,
        rate_hz: float = 20.0,
    ):
        self.drone_id = drone_id
        self.bus = bus
        self.host = host
        self.subject = subject
        self.segment = segment or subject  # single-segment objects: segment name == subject name
        self.rate_hz = rate_hz

        self.is_running = False
        self.is_connected = False
        self.latest: dict[str, Any] = {}

        self._loop: asyncio.AbstractEventLoop | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._pose_pending = False  # True while one vicon publish is scheduled/running on the loop

    # ------------------------------------------------------------ public
    async def start(self) -> None:
        """Connect + start receiving in a background thread. Returns immediately;
        connection result arrives as ack.vicon.* / error.vicon.* on the bus."""
        if self.is_running:
            return
        self._loop = asyncio.get_running_loop()
        self._stop.clear()
        self.is_running = True
        self._thread = threading.Thread(target=self._run, name=f"vicon-{self.subject}", daemon=True)
        self._thread.start()

    async def stop(self) -> None:
        self._stop.set()
        thread, self._thread = self._thread, None
        if thread is not None:
            await asyncio.to_thread(thread.join, 2.0)
        self.is_running = False

    # ------------------------------------------------------------ thread
    def _publish(self, topic: str, data: dict) -> None:
        """Thread -> event loop. Fire and forget."""
        if self.bus is None or self._loop is None or self._loop.is_closed():
            return
        try:
            asyncio.run_coroutine_threadsafe(self.bus.publish(topic, data), self._loop)
        except RuntimeError:
            pass  # loop already closed (shutdown)

    def _publish_latest_pose(self) -> None:
        """Thread -> event loop, latest-only: if a publish is still pending, do
        nothing - that pending publish will pick up the newest `latest` anyway."""
        if self._pose_pending or self.bus is None or self._loop is None or self._loop.is_closed():
            return
        self._pose_pending = True
        try:
            self._loop.call_soon_threadsafe(self._start_pose_publish)
        except RuntimeError:
            self._pose_pending = False  # loop already closed (shutdown)

    def _start_pose_publish(self) -> None:
        """Runs on the event loop."""
        asyncio.ensure_future(self._pose_publish())

    async def _pose_publish(self) -> None:
        try:
            await self.bus.publish(f"vicon.{self.drone_id}", self.latest)  # read NOW = newest sample
        finally:
            self._pose_pending = False

    def _run(self) -> None:
        try:
            from vicon_dssdk import ViconDataStream
        except ModuleNotFoundError as e:
            self._publish(
                f"error.vicon.{self.drone_id}", {"error": "ModuleNotFoundError", "message": f"{e} - install the Vicon DataStream SDK python wrapper."}
            )
            self.is_running = False
            return

        client = ViconDataStream.Client()
        try:
            client.Connect(self.host)
            if not client.IsConnected():
                raise RuntimeError("IsConnected() is False")
            client.EnableSegmentData()
            pull_mode = self._set_latest_frame_mode(client, ViconDataStream)
        except Exception as e:
            self._publish(f"error.vicon.{self.drone_id}", {"error": "ConnectFailed", "message": f"Could not connect to Vicon at {self.host}: {e}"})
            self.is_running = False
            return

        self.is_connected = True
        self._publish(f"ack.vicon.{self.drone_id}", {"cmd": "connect", "ack": "True", "host": self.host, "subject": self.subject})

        period = 1.0 / self.rate_hz if self.rate_hz > 0 else 0.0
        last_pub = 0.0
        last_error = None
        frame = 0
        try:
            while not self._stop.is_set():
                if pull_mode and period > 0:
                    # ClientPull: GetFrame() fetches the newest frame on request, so there is
                    # no need to read every Vicon frame - only grab one when it is time to publish.
                    wait = period - (time.monotonic() - last_pub)
                    if wait > 0 and self._stop.wait(wait):
                        break
                try:
                    client.GetFrame()
                    frame += 1
                    data = self._read_pose(client, frame)
                    last_error = None
                except Exception as e:
                    # e.g. subject not in the scene / no frame yet - report once, keep trying
                    msg = str(e)
                    if msg != last_error:
                        self._publish(f"error.vicon.{self.drone_id}", {"error": type(e).__name__, "message": msg, "subject": self.subject})
                        last_error = msg
                    time.sleep(0.1)
                    continue

                self.latest = data
                now = time.monotonic()
                if pull_mode or now - last_pub >= period:  # pull mode: the wait above already did the throttling
                    last_pub = now
                    self._publish_latest_pose()
        finally:
            try:
                client.Disconnect()
            except Exception:
                pass
            self.is_connected = False
            self._publish(f"ack.vicon.{self.drone_id}", {"cmd": "disconnect", "ack": "True", "host": self.host})

    def _set_latest_frame_mode(self, client, ViconDataStream) -> bool:
        """ClientPull + buffer 1 = GetFrame() always returns the newest frame.
        Returns True if ClientPull is active. If this SDK version lacks these calls,
        we stay in its default mode and simply read every frame (also no backlog)."""
        try:
            client.SetBufferSize(1)
        except Exception:
            pass
        try:
            client.SetStreamMode(ViconDataStream.Client.StreamMode.EClientPull)
            return True
        except Exception as e:
            self._publish(
                f"error.vicon.{self.drone_id}", {"error": "StreamModeNotSet", "message": f"No ClientPull, reading every frame instead: {e}"}
            )
            return False

    def _read_pose(self, client, frame: int) -> dict:
        translation, occluded_t = client.GetSegmentGlobalTranslation(self.subject, self.segment)
        quaternion, occluded_r = client.GetSegmentGlobalRotationQuaternion(self.subject, self.segment)
        data: dict[str, Any] = {"ts": time.time(), "frame": frame, "subject": self.subject, "occluded": bool(occluded_t or occluded_r)}

        qx, qy, qz, qw = quaternion
        if data["occluded"] or (qx == 0 and qy == 0 and qz == 0 and qw == 0):  # zero quaternion = no valid data
            data["occluded"] = True
            return data

        x, y, z = translation
        roll, pitch, yaw = quat_to_euler_xyz(qx, qy, qz, qw)
        data.update(
            {
                "x": float(x),
                "y": float(y),
                "z": float(z),
                "roll": roll,
                "pitch": pitch,
                "yaw": yaw,
                "qx": float(qx),
                "qy": float(qy),
                "qz": float(qz),
                "qw": float(qw),
            }
        )
        return data
