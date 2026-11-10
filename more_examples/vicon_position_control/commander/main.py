"""
# vicon_position_control - fly to / hold positions measured by the Vicon system

## You need
    Tello EDU / Talent on the Vicon lab network (station mode), vicon_dssdk, the drone as a
    subject in Vicon Tracker with its local x axis = the drone's nose. Free flight space!

## Run
    python run.py run -m -n vicon_position_control

## What it does
    C connect, V arm, T takeoff, then:
        9   fly to the next point of [control] waypoints (defaults.toml) and hold it there
        0   stop controlling (hover); manual keys work again
    20x per second: target - Vicon position -> turned into the drone's frame -> rc (commander/control.py).
    Safety: no fresh Vicon data for STALE_S or the subject is occluded -> rc 0 (hover).
    Errors, target and state are shown top-right on the video.
"""

import asyncio
import time

from control import Gains, distance_mm, rc_to_target

from core.controller import ControllerType, get_controller
from core.logger import LoggerType, get_logger
from core.vicon import get_vicon
from core.video import VideoOutputType, get_videostream
from projects.base import ProjectBase

RATE_HZ = 20
STALE_S = 0.3  # Vicon data older than this -> hover
ARRIVED_MM = 100


class vicon_position_control(ProjectBase):
    async def setup(self) -> None:
        self.live_logger = get_logger(
            LoggerType.LIVE_CONSOLE,
            min_level=self.log_level,
            exclude_topics=("frame.*", "vicon.*", "display.*", "data.stream.*"),
            exclude_data=("rc", "rc *"),
        )
        self.recorder.exclude_topics = ("frame.*", "display.*")
        self.recorder.attach(self.bus)
        self.bus.subscribe("*", self.live_logger.log_bus_event)

        self.drone1 = self.create_drone("drone_1")
        self.drone_id = self.drone1.drone_id
        self.video1 = get_videostream(
            VideoOutputType.CV2, drone_id=self.drone_id, bus=self.bus, media_dir=self.log_dir / "media", **self.app_config.get("video", {})
        )
        self.vicon = get_vicon(drone_id=self.drone_id, bus=self.bus, **self.app_config.get("vicon", {}))
        layout = self.app_config.get("controller", {}).get("layout")
        self.controller = get_controller(ControllerType.KEYBOARD, drone_id=self.drone_id, bus=self.bus, layout=layout)

        control = self.app_config.get("control", {})
        self.waypoints = [dict(zip(("x", "y", "z", "yaw"), p)) for p in control.get("waypoints", [[0, 0, 1000, 0]])]
        self.gains = Gains(**control.get("gains", {}))
        self.next_index = 0
        self.control_task: asyncio.Task | None = None
        self.bus.subscribe(f"project.{self.drone_id}", self.on_key)

    async def main(self) -> None:
        await self.controller.start_controller()
        await self.video1.start_stream()
        await self.vicon.start()
        print(self.controller.controls_text())
        print(f"9 = fly to next waypoint ({len(self.waypoints)}: {self.waypoints})  |  0 = stop")
        await asyncio.Event().wait()

    async def on_key(self, topic: str, data: dict) -> None:
        if data.get("action") == "misc_1":
            target = self.waypoints[self.next_index]
            self.next_index = (self.next_index + 1) % len(self.waypoints)
            await self.stop_control()
            self.control_task = asyncio.create_task(self.hold(target))
        elif data.get("action") == "misc_2":
            await self.stop_control()

    async def hold(self, target: dict) -> None:
        """Fly to target and hold it until stopped."""
        print(f"target {target}")
        try:
            while True:
                if self.drone1.flight_state.value != "inair":
                    await self.show({"control": "not flying - press T first"})
                    return
                pose = self.vicon.latest
                fresh = pose and not pose.get("occluded") and time.time() - pose.get("ts", 0) < STALE_S
                if fresh:
                    rc = rc_to_target(pose, target, self.gains)
                    dist = distance_mm(pose, target)
                    await self.show(
                        {
                            "control": "HOLDING" if dist < ARRIVED_MM else "flying to target",
                            "target [mm]": f"{target['x']:.0f} {target['y']:.0f} {target['z']:.0f}",
                            "distance [mm]": round(dist),
                            "rc": f"x {rc['x']:+.2f} y {rc['y']:+.2f} z {rc['z']:+.2f} yaw {rc['yaw']:+.2f}",
                        }
                    )
                else:
                    rc = {"x": 0, "y": 0, "z": 0, "yaw": 0}
                    await self.show({"control": "NO VICON DATA - hovering"})
                await self.send("rc", rc)
                await asyncio.sleep(1 / RATE_HZ)
        finally:
            if self.drone1.flight_state.value == "inair":
                await self.send("rc", {"x": 0, "y": 0, "z": 0, "yaw": 0})

    async def stop_control(self) -> None:
        if self.control_task is not None and not self.control_task.done():
            self.control_task.cancel()
            try:
                await self.control_task
            except asyncio.CancelledError:
                pass
            await self.show({"control": "stopped"})

    async def show(self, block: dict) -> None:
        await self.bus.publish(f"display.{self.drone_id}", block)

    async def send(self, action: str, args: dict | None = None) -> None:
        await self.bus.publish(f"cmd.{self.drone_id}", {"action": action, "args": args or {}, "source": "vicon_control"})

    async def end_run(self) -> None:
        await self.stop_control()
        await self.vicon.stop()
        await self.shutdown_drone(self.drone1)
        if self.video1.is_running:
            await self.video1.stop_stream()
        await self.controller.stop_controller()
        self.recorder.detach(self.bus)
