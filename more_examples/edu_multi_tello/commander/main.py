"""
# edu_multi_tello - several Tellos at once: mirrored keyboard flight + patterns in parallel

## You need
    2+ Tello EDU / Tello Talent (the basic Tello can't join a network), one Wi-Fi router.

## Setup (once per drone) - every drone must join the SAME router (station mode)
    1. Turn on ONE Tello, connect the PC to its hotspot TELLO-xxxxxx.
    2. python -m tools.set_tello_wifi --ssid <router wifi> --password <password>
       It reboots and joins the router. Repeat for every drone.
    3. Router: give each Tello a fixed IP (DHCP reservation by MAC), or read the IPs
       from its client list. Put them in config/mydrone.json.
    4. Connect the PC to the same router. Firewall: allow inbound UDP for every drone's
       cmd_pc_port / state_port / video_port (see mydrone.json).
    Back to hotspot mode: hold the Tello's power button ~5 s.

## config/mydrone.json
    One entry per drone ("drone_1", "drone_2", ...). Each needs its OWN cmd_pc_port,
    state_port and video_port - DFU tells the drone its ports on connect.

## Run
    python run.py run -m -n edu_multi_tello

## What it does
    Every key goes to ALL drones (one keyboard controller per drone): C connects all,
    V arms all, T takes all off, W/A/S/D + arrows fly all together.
        9   all drones fly PATTERN at the same time (core.patterns)
        0   stop the patterns (all hover)
    [multi] video = true opens one video window per drone (Wi-Fi bandwidth!).
"""

import asyncio

from core.controller import ControllerType, get_controller
from core.logger import LoggerType, get_logger
from core.patterns import get_patterns
from core.video import VideoOutputType, get_videostream
from projects.base import ProjectBase

PATTERN = ("square", {"side_cm": 100})  # method of core.patterns + kwargs


class edu_multi_tello(ProjectBase):
    async def setup(self) -> None:
        self.live_logger = get_logger(LoggerType.LIVE_CONSOLE, min_level=self.log_level, exclude_topics=("frame.*", "display.*", "state.*"))
        self.recorder.attach(self.bus)
        self.bus.subscribe("*", self.live_logger.log_bus_event)

        layout = self.app_config.get("controller", {}).get("layout")
        with_video = bool(self.app_config.get("multi", {}).get("video", False))
        self.drones, self.controllers, self.patterns, self.videos = [], [], [], []
        for key in sorted(k for k in self.drone_config if k.startswith("drone_")):
            drone = self.create_drone(key)
            self.drones.append(drone)
            self.controllers.append(get_controller(ControllerType.KEYBOARD, drone_id=drone.drone_id, bus=self.bus, layout=layout))
            self.patterns.append(get_patterns(drone.drone_id, self.bus))
            if with_video:
                self.videos.append(get_videostream(VideoOutputType.CV2, drone_id=drone.drone_id, bus=self.bus, media_dir=self.log_dir / "media"))
        # misc keys arrive once per controller (= once per drone) - react to drone_1's only
        self.bus.subscribe(f"project.{self.drones[0].drone_id}", self.on_key)
        print(f"{len(self.drones)} drones: " + ", ".join(f"{d.drone_id} @ {d.ip}" for d in self.drones))

    async def main(self) -> None:
        for controller in self.controllers:
            await controller.start_controller()
        for video in self.videos:
            await video.start_stream()
        print(self.controllers[0].controls_text())
        print(f"(every key goes to all {len(self.drones)} drones)  9 = all fly {PATTERN[0]}  |  0 = stop")
        await asyncio.Event().wait()

    async def on_key(self, topic: str, data: dict) -> None:
        if data.get("action") == "misc_1":
            method, kwargs = PATTERN
            for patterns in self.patterns:  # started together, each drone flies its own copy
                patterns.start(getattr(patterns, method)(**kwargs))
        elif data.get("action") == "misc_2":
            await asyncio.gather(*(p.cancel() for p in self.patterns))

    async def end_run(self) -> None:
        await asyncio.gather(*(p.cancel() for p in self.patterns))
        for p in self.patterns:
            p.detach()
        await asyncio.gather(*(self.shutdown_drone(d) for d in self.drones))  # all land at the same time
        for video in self.videos:
            if video.is_running:
                await video.stop_stream()
        for controller in self.controllers:
            await controller.stop_controller()
        self.recorder.detach(self.bus)
