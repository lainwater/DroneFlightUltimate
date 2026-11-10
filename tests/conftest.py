"""
Shared test helpers. No hardware, no window, no network beyond localhost.

    fake_tello   a fake Tello on 127.0.0.1 (real UDP): answers commands, sends state packets
    free_port()  a free local UDP port
    load_helper  import a helper file of a project (e.g. more_examples/x/commander/control.py)
"""

import importlib.util
import socket
import sys
import threading
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


ANSWERS = {
    "battery?": "87",
    "height?": "10dm",
    "temp?": "60~63C",
    "tof?": "100mm",
    "attitude?": "pitch:1;roll:2;yaw:3;",
    "acceleration?": "agx:1.00;agy:2.00;agz:-1000.00;",
    "time?": "12s",
    "sdk?": "30",
    "EXT tof?": "tof 1234",
}


class FakeTello:
    """Listens on (127.0.0.1, port). Every command is recorded in .got.
    Sends a state packet to (sender ip, state_port) every 50 ms after the first command."""

    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("127.0.0.1", 0))
        self.port = self.sock.getsockname()[1]
        self.got: list[str] = []
        self.peer = None
        self.state_port: int | None = None
        self.state = (
            "mid:4;x:10;y:20;z:80;mpry:0,30,0;pitch:1;roll:2;yaw:90;vgx:0;vgy:0;vgz:0;"
            "templ:60;temph:63;tof:10;h:80;bat:87;baro:1.2;time:5;agx:0;agy:0;agz:-1000;\r\n"
        )
        self.reply = "ok"
        self.move_delay = 0.0  # >0: moves answer after this long (like a real flight)
        self._stop = threading.Event()
        threading.Thread(target=self._loop, daemon=True).start()
        threading.Thread(target=self._state_loop, daemon=True).start()

    def _loop(self):
        self.sock.settimeout(0.1)
        while not self._stop.is_set():
            try:
                data, addr = self.sock.recvfrom(1024)
            except (TimeoutError, OSError):
                continue
            msg = data.decode()
            self.got.append(msg)
            self.peer = addr
            if msg.startswith("port "):
                self.state_port = int(msg.split()[1])
            if msg.startswith("rc ") or msg == "stop":
                continue  # the real Tello doesn't answer these
            answer = ANSWERS.get(msg, self.reply).encode()
            if self.move_delay and msg.split()[0] in ("forward", "back", "left", "right", "up", "down", "cw", "ccw", "go"):
                threading.Timer(self.move_delay, self.sock.sendto, (answer, addr)).start()
            else:
                self.sock.sendto(answer, addr)

    def _state_loop(self):
        out = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        while not self._stop.is_set():
            time.sleep(0.05)
            if self.peer and self.state_port:
                try:
                    out.sendto(self.state.encode(), ("127.0.0.1", self.state_port))
                except OSError:
                    pass
        out.close()

    def close(self):
        self._stop.set()
        self.sock.close()


@pytest.fixture
def fake_tello():
    t = FakeTello()
    yield t
    t.close()


def tello_kwargs(fake: FakeTello, **extra) -> dict:
    """Drone kwargs that point a TelloDrone at the fake (free local ports)."""
    state_port = free_port()
    fake.state_port = state_port
    return {"ip": "127.0.0.1", "cmd_port": fake.port, "cmd_pc_port": free_port(), "state_port": state_port, "video_port": free_port(), **extra}


def load_helper(path: Path, name: str):
    """Import one helper .py file under a unique module name."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module
