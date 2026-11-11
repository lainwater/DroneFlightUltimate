"""
# fly_to_marker - find an ArUco marker and hold position in front of it

## You need
    Any Tello (basic, EDU, Talent) with a calibration for its camera ([video] calibration),
    a printed marker TARGET_ID of [video] aruco_dictionary with the black square measured
    into aruco_marker_size (metres). Free space between drone and marker!

## Run
    python run.py run -m -n fly_to_marker

## What it does
    C connect, V arm, J video, T takeoff, then:
        9   start following: turn towards TARGET_ID, fly to Gains.distance_m in front of it,
            keep it in the image centre (up/down) - also when the marker moves
        0   stop following (hover)
    Marker lost for more than LOST_S: hover (or turn slowly to search, SEARCH_YAW).
    Any manual key still works; while following, the controller overrides it 10x per second.
    The control law is commander/control.py (pure, tested).
"""

import asyncio
import time

from control import Gains, arrived, rc_to_marker

from core.controller import ControllerType, get_controller
from core.logger import LoggerType, get_logger
from core.video import VideoOutputType, get_videostream
from projects.base import ProjectBase

TARGET_ID = 1  # marker to fly to (other markers are ignored)
GAINS = Gains(distance_m=1.0, max_rc=0.3)
RATE_HZ = 10
LOST_S = 0.5  # marker not seen this long -> hover
SEARCH_YAW = 0.15  # >0: turn this fast (rc) while the marker is lost, e.g. 0.15


class fly_to_marker(ProjectBase):
    async def setup(self) -> None:
        self.live_logger = get_logger(
            LoggerType.LIVE_CONSOLE,
            min_level=self.log_level,
            exclude_topics=("frame.*", "data.stream.*", "display.*", "state.*"),
            exclude_data=("rc", "rc *"),
        )
        self.recorder.attach(self.bus)
        self.bus.subscribe("*", self.live_logger.log_bus_event)

        self.drone1 = self.create_drone("drone_1")
        self.drone_id = self.drone1.drone_id
        self.video1 = get_videostream(
            VideoOutputType.CV2, drone_id=self.drone_id, bus=self.bus, media_dir=self.log_dir / "media", **self.app_config.get("video", {})
        )
        layout = self.app_config.get("controller", {}).get("layout")
        self.controller = get_controller(ControllerType.KEYBOARD, drone_id=self.drone_id, bus=self.bus, layout=layout)

        self.marker: dict | None = None
        self.marker_time = 0.0
        self.follow_task: asyncio.Task | None = None
        self.bus.subscribe(f"data.stream.{self.drone_id}", self.on_markers)
        self.bus.subscribe(f"project.{self.drone_id}", self.on_key)

    async def main(self) -> None:
        await self.controller.start_controller()
        await self.video1.start_stream()
        await self.video1.start_aruco(publish=True)
        print(self.controller.controls_text())
        print(f"9 = follow marker {TARGET_ID} at {GAINS.distance_m} m  |  0 = stop")
        await asyncio.Event().wait()

    async def on_markers(self, topic: str, data: dict) -> None:
        for m in data.get("aruco") or []:
            if m["id"] == TARGET_ID and "z" in m:  # "z" only with a calibration
                self.marker, self.marker_time = m, time.monotonic()

    async def on_key(self, topic: str, data: dict) -> None:
        if data.get("action") == "misc_1" and not self.following():
            self.follow_task = asyncio.create_task(self.follow())
        elif data.get("action") == "misc_2":
            await self.stop_following()

    async def follow(self) -> None:
        print(f"following marker {TARGET_ID}")
        try:
            while True:
                if self.drone1.flight_state.value != "inair":
                    await self.show("not flying - press T first")
                    return
                fresh = self.marker is not None and time.monotonic() - self.marker_time < LOST_S
                if fresh:
                    rc = rc_to_marker(self.marker, GAINS)
                    state = "ARRIVED" if arrived(self.marker, GAINS) else "approaching"
                    await self.show(f"{state} z={self.marker['z']:.2f} m x={self.marker['x']:+.2f}")
                else:
                    rc = {"x": 0, "y": 0, "z": 0, "yaw": SEARCH_YAW}
                    await self.show("marker lost - " + ("searching" if SEARCH_YAW else "hovering"))
                await self.send("rc", rc)
                await asyncio.sleep(1 / RATE_HZ)
        finally:
            if self.drone1.flight_state.value == "inair":
                await self.send("rc", {"x": 0, "y": 0, "z": 0, "yaw": 0})

    async def stop_following(self) -> None:
        if self.following():
            self.follow_task.cancel()
            try:
                await self.follow_task
            except asyncio.CancelledError:
                pass
            await self.show("stopped")

    def following(self) -> bool:
        return self.follow_task is not None and not self.follow_task.done()

    async def show(self, text: str) -> None:
        await self.bus.publish(f"display.{self.drone_id}", {"follow": text})

    async def send(self, action: str, args: dict | None = None) -> None:
        await self.bus.publish(f"cmd.{self.drone_id}", {"action": action, "args": args or {}, "source": "fly_to_marker"})

    async def end_run(self) -> None:
        await self.stop_following()
        await self.shutdown_drone(self.drone1)
        if self.video1.is_running:
            await self.video1.stop_stream()
        await self.controller.stop_controller()
        self.recorder.detach(self.bus)
