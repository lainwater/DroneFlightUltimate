"""
camera - live frames for the calibration tool, standalone (cv2 + standard library only).

    cam = open_camera("webcam", index=0)            # laptop / USB camera
    cam = open_camera("tello", ip="192.168.10.133") # Tello: 'command' + 'streamon', video via FFmpeg
    frame = cam.read()                               # NEWEST frame (older ones are dropped)
    cam.close()

The Tello's video is read in a thread that always keeps only the newest frame, so a
slow loop (chessboard search) never builds up lag.
"""

import socket
import threading
import time

import cv2 as cv

TELLO_PORT = 8889
LOCAL_PORT = 9000
TELLO_VIDEO = "udp://0.0.0.0:11111"


class Camera:
    def __init__(self, capture, name: str):
        self.capture = capture
        self.name = name

    def read(self, timeout: float = 10.0):
        ok, frame = self.capture.read()
        if not ok or frame is None:
            raise RuntimeError(f"No frame from {self.name}.")
        return frame

    def close(self) -> None:
        self.capture.release()


class TelloCamera(Camera):
    """Tello video in a reader thread (latest frame only)."""

    def __init__(self, ip: str, local_port: int = LOCAL_PORT):
        self.ip = ip
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("", local_port))
        self.sock.settimeout(5)
        for command in ("command", "streamon"):
            answer = self._send(command)
            if answer is None:
                self.sock.close()
                raise ConnectionError(f"No answer from the Tello at {ip} (network? firewall: inbound UDP {local_port} and 11111).")
            if not answer.lower().endswith("ok"):
                self.sock.close()
                raise ConnectionError(f"Tello answered {answer!r} to {command!r}.")
        super().__init__(cv.VideoCapture(TELLO_VIDEO, cv.CAP_FFMPEG), f"Tello {ip}")
        self._lock = threading.Lock()
        self._frame = None
        self._seq = 0
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._reader, daemon=True)
        self._thread.start()

    def _send(self, command: str) -> str | None:
        self.sock.sendto(command.encode(), (self.ip, TELLO_PORT))
        try:
            return self.sock.recvfrom(1024)[0].decode(errors="replace").strip()
        except (socket.timeout, ConnectionResetError):
            return None

    def _reader(self) -> None:
        while not self._stop.is_set():
            ok, frame = self.capture.read()
            if ok and frame is not None:
                with self._lock:
                    self._frame, self._seq = frame, self._seq + 1
            else:
                time.sleep(0.01)

    def read(self, timeout: float = 10.0):
        """Wait for a frame newer than the last one returned."""
        last = getattr(self, "_returned", 0)
        t_end = time.monotonic() + timeout
        while time.monotonic() < t_end:
            with self._lock:
                if self._seq != last and self._frame is not None:
                    self._returned = self._seq
                    return self._frame.copy()
            time.sleep(0.005)
        raise TimeoutError(f"No video from the Tello at {self.ip} (firewall: inbound UDP 11111?).")

    def close(self) -> None:
        self._stop.set()
        self._thread.join(timeout=1)
        try:
            self.sock.sendto(b"streamoff", (self.ip, TELLO_PORT))
        finally:
            self.sock.close()
            super().close()


def open_camera(camera: str = "tello", ip: str = "192.168.10.1", index: int = 0) -> Camera:
    if camera == "tello":
        return TelloCamera(ip)
    if camera == "webcam":
        cap = cv.VideoCapture(index)
        if not cap.isOpened():
            raise RuntimeError(f"Could not open camera {index} (used by another app? other --index?)")
        return Camera(cap, f"camera {index}")
    raise ValueError("camera must be 'tello' or 'webcam'")
