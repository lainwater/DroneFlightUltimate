"""
CV2Display - Output frames to cv2 window from Bus
"""

from datetime import datetime
from pathlib import Path

import cv2 as cv

from core.video.base import VideoBase

TEXT_SPACING = 40


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
        frame = await self._data_to_frame(data)
        self._latest_frame = frame.copy()
        if self.recorder.is_recording:
            self.recorder.write(self._latest_frame)
        await self._display_text(frame, text=self.drone_id, position=(30, 50))
        if self.display_state_data:
            i = 0
            for item in self.data_to_display:
                i += 1
                if item == "ts" or item == "timestamp":
                    await self._display_text(frame, text=f"{self.ts}", position=(20, 80 + i * TEXT_SPACING))
                elif item == "fps":
                    delta = float(ts_fps_new) - float(self.ts_fps_old)
                    fps = 1 / delta if delta > 0 else 0.0
                    await self._display_text(frame, text=f"FPS: {fps:.1f}", position=(20, 80 + i * TEXT_SPACING))
                    self.ts_fps_old = ts_fps_new
                else:
                    try:
                        await self._display_text(frame, text=f"{item}: {self.state_data[item]}", position=(20, 80 + i * TEXT_SPACING))
                    except (KeyError, TypeError):
                        pass

        if self.rescale_factor != 1:
            frame = await self._rescale_frame(frame, self.rescale_factor)

        if self.fpv_goggles_mode:
            frame = await self._to_fpv_goggles_frame(frame)

        cv.imshow(self.drone_id, frame)
        cv.waitKey(1)

    async def _rescale_frame(self, frame, scale):
        width = int(frame.shape[1] * scale)
        height = int(frame.shape[0] * scale)
        dimensions = (width, height)
        return cv.resize(frame, dimensions, interpolation=cv.INTER_AREA)

    async def _to_fpv_goggles_frame(self, frame):
        h, w = frame.shape[:2]
        side = min(h, w)
        x0 = (w - side) // 2
        y0 = (h - side) // 2
        square = frame[y0 : y0 + side, x0 : x0 + side]
        return cv.hconcat([square, square])

    async def _display_text(self, frame, text=None, position=(30, 50), font=cv.FONT_HERSHEY_SIMPLEX, font_scale=1, color=(255, 0, 115), thickness=2):
        """Render text on frame"""
        cv.putText(frame, text, position, font, font_scale, color, thickness)

    async def _data_to_frame(self, data):
        """Turn a frame.{drone_id} bus message into a BGR numpy frame."""
        payload = data.get("frame", None)
        if payload is None:
            raise ValueError("frame event carried no 'frame' payload")
        encoding = data.get("encoding", "bgr24")
        if encoding == "bgr24":
            return payload
        if encoding == "jpeg":
            import numpy as np

            return cv.imdecode(np.frombuffer(payload, dtype=np.uint8), cv.IMREAD_COLOR)
        raise ValueError(f"Unsupported frame encoding: {encoding!r}")
