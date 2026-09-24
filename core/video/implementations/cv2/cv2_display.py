"""
CV2Display - Output frames to cv2 window from Bus
"""

from datetime import datetime
from pathlib import Path

import cv2 as cv

from core.video.base import VideoBase


class CV2Display(VideoBase):
    def __init__(self, drone_id: str, bus: object, **kwargs):
        super().__init__(drone_id, bus, **kwargs)
        self.cap = None
        self.ts_fps_old = datetime.timestamp(datetime.now())

    @property
    def config_dir(self) -> Path:
        return Path(__file__).parent

    async def start_stream(self):
        """Start the video stream."""
        # drone needs to do this first for telllo:
        # set video port .send_and_receive(f"port {self.info_port} {self.video_port}")
        # self.drone.send_and_receive("streamon")
        # self.cap = await cv.VideoCapture(self.udp)
        # self.cap.release()
        self._attach()
        cv.namedWindow(self.drone_id)
        self.is_running = True

    async def stop_stream(self):
        """Stop the video stream."""
        cv.destroyWindow(self.drone_id)
        self._detach()
        self.is_running = False

    async def _update_frame(self, data):
        """Update displayed frame"""
        ts_fps_new = datetime.timestamp(datetime.now())
        recieved = data.get("recieved", False)
        frame = self.data_to_frame(data.get("frame", False))

        await self._display_text(text=self.drone_id, position=(30, 50))
        if self.display_state_data:
            i = 0
            for item in self.data_to_display:
                i += 1
                if item == "ts" or item == "timestamp":
                    await self._display_text(frame, text=f"{self.ts}", position=(20, 40))
                elif item == "fps":
                    fps = 1 / (float(ts_fps_new) - float(self.ts_fps_old))
                    await self._display_text(frame, text=f"FPS: {fps}", position=(20, 40))
                    self.ts_fps_old = ts_fps_new
                else:
                    try:
                        await self._display_text(frame, text=f"{item}: {self.state_data[item]}", position=(20, 60 + i * 10))
                    except KeyError or TypeError:
                        pass

        if self.rescale_factor != 1:
            frame = await self._rescale_frame(frame, self.rescale_factor)

        if self.fpv_goggles_mode:
            frame = await self._to_fpv_goggles_frame(frame)

        cv.imshow(self.drone_id, frame)

    async def _rescale_frame(self, frame, scale):
        """Rescale frame"""
        width = int(frame.shape[1] * scale)
        height = int(frame.shape[0] * scale)
        dimensions = (width, height)
        return cv.resize(frame, dimensions, interpolation=cv.INTER_AREA)

    async def _to_fpv_goggles_frame(self, frame):
        """Change frame to FPV-Goggles look"""
        if not self.fpv_goggles_mode:
            return

    async def _display_text(self, frame, text=None, position=(30, 50), font=cv.FONT_HERSHEY_SIMPLEX, font_scale=1, color=(255, 0, 115), thickness=2):
        """Render text on frame"""
        cv.putText(frame, text, position, font, font_scale, color, thickness)

    async def _data_to_frame(self, data):
        # needs to convert data to frame, im not sure what format im using yet tho
        raise NotImplementedError
