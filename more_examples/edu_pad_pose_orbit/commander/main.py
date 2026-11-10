"""
# edu_pad_pose_orbit - mission pads, an orbit, a dance and YOLO on a Tello EDU

## You need
    Tello EDU or Tello Talent (mission pads), its mission pads on the floor,
    ultralytics for YOLO (pip install -U ultralytics).

## Run
    python run.py run -m -n edu_pad_pose_orbit

## What it does
    - connects, arms, turns on mission-pad detection, telemetry, video and YOLO by itself
    - key 9: flies an orbit (circle, nose to the centre) and records it to a video
    - key 0: stops the orbit / dance (drone hovers)
    - over pad DANCE_PAD: dances (at most every DANCE_COOLDOWN_S)
    - over any pad in PADS: shows the drone's pose in the world (x, y, yaw) top-right -
      standard right-handed frame, yaw counter-clockwise from +x (see pose.py)
    - sees a cell phone (YOLO, conf > PHONE_MIN_CONF): stops and lands

Files: main.py (wiring + handlers), pose.py (pure pose math, tested in tests/).
Flight moves come from core.patterns (orbit, dance).
"""

import asyncio
import time

from pose import world_pose  # commander/pose.py - helper files next to main.py import by name

from core.controller import ControllerType, get_controller
from core.logger import LoggerType, get_logger
from core.patterns import get_patterns
from core.video import VideoOutputType, get_videostream
from projects.base import ProjectBase

DANCE_PAD = 6  # mission pad that triggers the dance
DANCE_COOLDOWN_S = 10.0
PHONE_LABEL = "cell phone"
PHONE_MIN_CONF = 0.85
ORBIT = {"radius_cm": 100, "speed_cms": 20, "laps": 1, "clockwise": True}  # + cms_per_rc / deg_per_s_per_rc calibration

# pad id: (x cm, y cm, rocket yaw deg) of each pad in the world frame (standard: right-handed,
# yaw = counter-clockwise angle of the pad's ROCKET from world +x). 90 = rocket along world +y.
PADS = {1: (-70, 80, 45), 2: (60, 100, 90), 3: (-62, -78, 45), 4: (50, -60, -90)}


class edu_pad_pose_orbit(ProjectBase):
    async def setup(self) -> None:
        self.live_logger = get_logger(
            LoggerType.LIVE_CONSOLE, min_level=self.log_level, exclude_topics=("frame.*", "state.*", "display.*", "data.stream.*")
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
        self.patterns = get_patterns(self.drone_id, self.bus)

        self._last_dance = -DANCE_COOLDOWN_S
        self._pose_shown = False
        self._landing = False

        self.bus.subscribe(f"project.{self.drone_id}", self.on_key)
        self.bus.subscribe(f"data.stream.{self.drone_id}", self.on_detections)
        self.bus.subscribe(f"state.{self.drone_id}", self.on_state)

    async def main(self) -> None:
        await self.controller.start_controller()
        print(self.controller.controls_text())
        for action in ("connect", "set_arm", "set_mission_pad_on", "start_state_receiver", "start_video"):
            await self.send(action)
        await self.video1.start_stream()
        await self.video1.turn_on_display_state_data()
        await self.video1.start_detection(publish=True)
        await asyncio.Event().wait()  # until CTRL+C

    async def end_run(self) -> None:
        await self.patterns.cancel()
        self.patterns.detach()
        await self.shutdown_drone(self.drone1)
        if self.video1.is_running:
            await self.video1.stop_recording()
            await self.video1.stop_stream()
        await self.controller.stop_controller()
        self.recorder.detach(self.bus)

    # ------------------------------------------------------------ bus handlers
    async def on_key(self, topic: str, data: dict) -> None:
        if data.get("action") == "misc_1":
            task = self.patterns.start(self.patterns.orbit(**ORBIT))
            if task is not None:
                asyncio.create_task(self._record_while(task))
        elif data.get("action") == "misc_2":
            await self.patterns.cancel()

    async def _record_while(self, task: asyncio.Task) -> None:
        await self.video1.start_recording()
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            pass
        finally:
            await self.video1.stop_recording()

    async def on_detections(self, topic: str, data: dict) -> None:
        """YOLO results: land as soon as a cell phone is seen."""
        for det in data.get("detections") or []:
            if det["label"] == PHONE_LABEL and det["conf"] > PHONE_MIN_CONF:
                await self.land_for_phone()
                return

    async def on_state(self, topic: str, data: dict) -> None:
        pad = data.get("mission_pad") or {}
        if pad.get("id") == DANCE_PAD and self.in_air() and time.monotonic() - self._last_dance > DANCE_COOLDOWN_S:
            task = self.patterns.start(self.patterns.dance())  # None if another pattern is running
            if task is not None:
                task.add_done_callback(lambda _: setattr(self, "_last_dance", time.monotonic()))  # cooldown from the END
        await self.show_pose(pad)

    # ------------------------------------------------------------ actions
    async def land_for_phone(self) -> None:
        if self._landing or not self.in_air():
            return
        self._landing = True
        try:
            print("phone detected: landing")
            await self.patterns.cancel()
            await self.send("land")
        finally:
            self._landing = False

    async def show_pose(self, pad: dict) -> None:
        """Drone pose in the world while it sees a pad from PADS, cleared otherwise."""
        pose = world_pose(PADS[pad["id"]], pad) if pad.get("id") in PADS else None
        if pose is None:
            if self._pose_shown:
                await self.bus.publish(f"display.{self.drone_id}", {})
                self._pose_shown = False
            return
        x, y, yaw = pose
        await self.bus.publish(f"display.{self.drone_id}", {"pad": pad["id"], "x (cm)": round(x), "y (cm)": round(y), "yaw (deg)": round(yaw)})
        self._pose_shown = True

    # ------------------------------------------------------------ helpers
    def in_air(self) -> bool:
        return self.drone1.flight_state.value == "inair"

    async def send(self, action: str, args: dict | None = None) -> None:
        await self.bus.publish(f"cmd.{self.drone_id}", {"action": action, "args": args or {}})
