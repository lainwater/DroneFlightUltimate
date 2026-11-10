"""
# tello_patterns - fly the predefined patterns of core.patterns

## You need
    Any Tello (basic, EDU, Talent) - or the simdrone (drone_type "sim_simdrone").
    About 2 x 2 m of free space.

## Run
    python run.py run -m -n tello_patterns

## What it does
    C connect, V arm, T takeoff, then:
        9   fly the next pattern of PATTERNS (square, triangle, hexagon, circle, ...)
        0   stop the pattern - the drone stops and hovers
    The current pattern is shown on the video. Any manual key still works.
"""

import asyncio

from core.controller import ControllerType, get_controller
from core.logger import LoggerType, get_logger
from core.patterns import get_patterns
from core.video import VideoOutputType, get_videostream
from projects.base import ProjectBase

# (name shown, method of core.patterns, kwargs) - all sizes in cm
PATTERNS = [
    ("square 100", "square", {"side_cm": 100}),
    ("triangle 100", "triangle", {"side_cm": 100}),
    ("hexagon 60", "hexagon", {"side_cm": 60}),
    ("circle r 80", "circle", {"radius_cm": 80, "segments": 12}),
    ("rectangle 150 x 80", "rectangle", {"length_cm": 150, "width_cm": 80}),
    ("waypoints", "waypoints", {"points": [(100, 0, 0), (100, 60, 40), (0, 60, 40), (0, 0, 0)]}),
    ("spin 360", "spin", {"degrees": 360}),
    ("orbit r 100", "orbit", {"radius_cm": 100, "speed_cms": 20}),
    ("dance", "dance", {}),
]


class tello_patterns(ProjectBase):
    async def setup(self) -> None:
        self.live_logger = get_logger(LoggerType.LIVE_CONSOLE, min_level=self.log_level, exclude_topics=("frame.*", "display.*"))
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
        self.next_index = 0
        self.current = ""

        self.bus.subscribe(f"project.{self.drone_id}", self.on_key)
        self.bus.subscribe(f"ack.patterns.{self.drone_id}", self.on_pattern_status)

    async def main(self) -> None:
        await self.controller.start_controller()
        await self.video1.start_stream()
        print(self.controller.controls_text())
        print("9 = next pattern:", ", ".join(name for name, _, _ in PATTERNS), "  |  0 = stop")
        await asyncio.Event().wait()

    async def on_key(self, topic: str, data: dict) -> None:
        if data.get("action") == "misc_1":
            if self.patterns.busy:
                print("a pattern is still running - 0 stops it")
                return
            name, method, kwargs = PATTERNS[self.next_index]
            self.next_index = (self.next_index + 1) % len(PATTERNS)
            self.current = name
            self.patterns.start(getattr(self.patterns, method)(**kwargs))
        elif data.get("action") == "misc_2":
            await self.patterns.cancel()

    async def on_pattern_status(self, topic: str, data: dict) -> None:
        """ack.patterns.<id>: started / done / cancelled / aborted (+ info)."""
        text = f"{self.current or data['pattern']}: {data['status']}"
        await self.bus.publish(f"display.{self.drone_id}", {"pattern": text, "info": data.get("info", "")})

    async def end_run(self) -> None:
        await self.patterns.cancel()
        self.patterns.detach()
        await self.shutdown_drone(self.drone1)
        if self.video1.is_running:
            await self.video1.stop_stream()
        await self.controller.stop_controller()
        self.recorder.detach(self.bus)
