"""
# edu_search_and_rescue - fly a lawnmower search and land on the target mission pad

## You need
    Tello EDU or Tello Talent (mission pads), mission pads on the floor, space for the search area.

## Run
    python run.py run -m -n edu_search_and_rescue

## What it does
    ^  lane 1   |  lane 3   ^  ...
    |           v           |       lanes LANE_LENGTH_CM long, LANE_SPACING_CM apart
    |  lane 2   |           |       (= ground width the camera sees). At the end of each lane
  start ---->   +---->      +       the drone steps over and turns 180 deg: always nose first.

    key 9   start the mission (takes off if needed, then searches)
    key 0   abort the search (drone stops and hovers)
    any manual flight key (arrows, W/A/S/D, T/L, Space) = YOU take over, the search stops

    As soon as pad TARGET_PAD_ID is seen: stop at once, centre above it, hover HOVER_S,
    optionally show the pad moves (PAD_DEMO: go / jump / curve to DEMO_PAD), land.
    The search is core.patterns' lawnmower; 'stop' interrupts a running move immediately.
"""

import asyncio

from core.controller import ControllerType, get_controller
from core.logger import LoggerType, get_logger
from core.patterns import get_patterns
from core.video import VideoOutputType, get_videostream
from projects.base import ProjectBase

# ---------------------------------------------------------------- search area
LANE_LENGTH_CM = 150  # length of each lane
LANE_SPACING_CM = 40  # distance between lanes = ground width the camera sees
AREA_WIDTH_CM = 160  # how far to the side the search goes
MAX_LANES = 8
SHIFT_RIGHT = False  # next lane to the right (False = left)
SEARCH_SPEED_CMS = 20  # 10..100; keep LANE_LENGTH_CM / speed under ~12 s
SETTLE_S = 1.0  # after 'stop': let the drone settle before the next command

# ---------------------------------------------------------------- target
TARGET_PAD_ID = 4  # only THIS pad ends the search
HOVER_HEIGHT_CM = 80  # height above the pad while hovering on it
HOVER_S = 3.0
LAND_IF_NOT_FOUND = True

# ---------------------------------------------------------------- pad demo after finding
PAD_DEMO = True
DEMO_PAD = 2  # second pad for go / jump / curve
DEMO_PAD_OFFSET = (-100, -20)  # where DEMO_PAD is seen from the target pad, in the Tello's pad frame (cm)
DEMO_GO_X_CM = 30
DEMO_HEIGHT_CM = 80
DEMO_SPEED_CMS = 20  # go / jump 10..100, curve 10..60

MANUAL_ACTIONS = {"rc", "takeoff", "land", "emergency"}  # keyboard actions that mean "I take over"


class edu_search_and_rescue(ProjectBase):
    async def setup(self) -> None:
        self.live_logger = get_logger(
            LoggerType.LIVE_CONSOLE, min_level=self.log_level, exclude_topics=("frame.*", "display.*", "data.stream.*", "state.*")
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

        self.search_task: asyncio.Task | None = None
        self.rescue_task: asyncio.Task | None = None

        self.bus.subscribe(f"project.{self.drone_id}", self.on_key)
        self.bus.subscribe(f"cmd.{self.drone_id}", self.on_command)
        self.bus.subscribe(f"state.{self.drone_id}", self.on_state)

    async def main(self) -> None:
        await self.controller.start_controller()
        print(self.controller.controls_text())
        for action, args in (
            ("connect", {}),
            ("set_arm", {}),
            ("set_mission_pad_on", {}),
            ("set_mission_pad_direction", {"direction": 0}),  # 0 = look down
            ("start_state_receiver", {}),
            ("start_video", {}),
        ):
            await self.send(action, args)
        await self.video1.start_stream()
        await self.video1.turn_on_display_state_data()
        await self.status("ready - press 9")
        await asyncio.Event().wait()

    async def end_run(self) -> None:
        await self.stop_search()
        self.patterns.detach()
        await self.shutdown_drone(self.drone1)
        if self.video1.is_running:
            await self.video1.stop_stream()
        await self.controller.stop_controller()
        self.recorder.detach(self.bus)

    # ------------------------------------------------------------ bus handlers
    async def on_key(self, topic: str, data: dict) -> None:
        if data.get("action") == "misc_1" and not self.searching() and not self.rescuing():
            self.search_task = asyncio.create_task(self.search())
        elif data.get("action") == "misc_2" and self.searching():
            await self.stop_search()
            await self.status("search aborted")

    async def on_command(self, topic: str, data: dict) -> None:
        """Every cmd.<id>. Commands from this project / core.patterns carry a "source";
        the keyboard's don't - a keyboard flight key means: human takes over."""
        if data.get("source"):
            return
        if self.searching() and data.get("action") in MANUAL_ACTIONS:
            print("manual control - search stopped")
            await self.stop_search()
            await self.status("MANUAL control")

    async def on_state(self, topic: str, data: dict) -> None:
        pad = data.get("mission_pad") or {}
        if pad.get("id") == TARGET_PAD_ID and self.in_air() and not self.rescuing():
            # own task: the state stream must keep running while we hover and land
            self.rescue_task = asyncio.create_task(self.land_on_target())

    # ------------------------------------------------------------ mission
    async def search(self) -> None:
        if not self.in_air():
            await self.send("takeoff")
            if not self.in_air():
                await self.status("takeoff failed")
                return
        await self.send("set_speed", {"speed": SEARCH_SPEED_CMS})
        lanes = min(MAX_LANES, AREA_WIDTH_CM // LANE_SPACING_CM + 1)
        print(f"search: {lanes} lanes x {LANE_LENGTH_CM} cm, {LANE_SPACING_CM} cm apart")
        await self.status(f"searching {lanes} lanes")
        task = self.patterns.start(self.patterns.lawnmower(LANE_LENGTH_CM, LANE_SPACING_CM, lanes, shift_right=SHIFT_RIGHT))
        if task is None:
            return
        await task
        print(f"search done - pad m{TARGET_PAD_ID} not found")
        await self.status("not found")
        if LAND_IF_NOT_FOUND and self.in_air():
            await self.send("land")

    async def land_on_target(self) -> None:
        print(f"\n{'=' * 40}\n  TARGET FOUND: mission pad m{TARGET_PAD_ID}\n{'=' * 40}")
        await self.stop_search()  # 'stop' -> drone brakes and hovers right here
        target = f"m{TARGET_PAD_ID}"
        await self.status(f"FOUND {target} - centering")
        await self.send("goto_mission_pad", {"x": 0, "y": 0, "z": HOVER_HEIGHT_CM, "speed": 20, "mid": target})
        await self.status(f"FOUND {target} - hovering")
        await self.patterns.hover(HOVER_S)  # rc keep-alive: the Tello lands itself after 15 s without commands

        landed_on = target
        if PAD_DEMO and self.in_air():
            await self.pad_demo()
            landed_on = f"m{DEMO_PAD}"
        if self.in_air():
            await self.status(f"landing on {landed_on}")
            await self.send("land")
        print(f"MISSION SUCCESS - landed on {landed_on}")
        await self.status(f"SUCCESS - landed on {landed_on}")

    async def pad_demo(self) -> None:
        """go / jump / curve between the target pad and DEMO_PAD. Coordinates are relative to
        a mission pad, so the drone corrects itself on every pad it reaches."""
        target, demo = f"m{TARGET_PAD_ID}", f"m{DEMO_PAD}"
        dx, dy = DEMO_PAD_OFFSET
        z, v = DEMO_HEIGHT_CM, DEMO_SPEED_CMS

        await self.status(f"go x {DEMO_GO_X_CM} on {target}")
        await self.send("goto_mission_pad", {"x": DEMO_GO_X_CM, "y": 0, "z": z, "speed": v, "mid": target})
        await self.status(f"back to the centre of {target}")
        await self.send("goto_mission_pad", {"x": 0, "y": 0, "z": z, "speed": v, "mid": target})

        await self.status(f"jump {target} -> {demo}")
        await self.send("jump", {"x": dx, "y": dy, "z": z, "speed": v, "yaw": 0, "mid1": target, "mid2": demo})
        await self.send("goto_mission_pad", {"x": 0, "y": 0, "z": z, "speed": v, "mid": demo})

        await self.status(f"curve over {demo}")
        await self.send("curve", {"x1": -50, "y1": -50, "z1": z, "x2": 50, "y2": 50, "z2": z, "speed": min(v, 60), "mid": demo})

    async def stop_search(self) -> None:
        """Stop NOW: the pattern is cancelled and 'stop' interrupts the running move."""
        if not self.searching() or self.search_task is asyncio.current_task():
            return
        await self.patterns.cancel()
        self.search_task.cancel()
        try:
            await self.search_task
        except asyncio.CancelledError:
            pass
        self.search_task = None
        await asyncio.sleep(SETTLE_S)  # drone settles, late answers of the interrupted move arrive

    # ------------------------------------------------------------ helpers
    def in_air(self) -> bool:
        return self.drone1.flight_state.value == "inair"

    def searching(self) -> bool:
        return self.search_task is not None and not self.search_task.done()

    def rescuing(self) -> bool:
        return self.rescue_task is not None and not self.rescue_task.done()

    async def send(self, action: str, args: dict | None = None) -> None:
        """Command over the bus; returns when the drone has answered. "source" marks it as ours."""
        await self.bus.publish(f"cmd.{self.drone_id}", {"action": action, "args": args or {}, "source": "sar"})

    async def status(self, text: str) -> None:
        await self.bus.publish(f"display.{self.drone_id}", {"SAR": text, "target": f"m{TARGET_PAD_ID}"})
