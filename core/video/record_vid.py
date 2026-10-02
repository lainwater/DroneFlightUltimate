"""
FrameRecorder - stream frames to an .mp4 file on disk while recording
is active. Used by VideoBase.start_recording()/stop_recording() - one
instance per VideoBase instance, shared across whichever concrete
display (CV2Display, WebServerDisplay, ...) owns it.
"""

from datetime import datetime
from pathlib import Path

import cv2 as cv


class FrameRecorder:
    def __init__(self, media_dir: Path, drone_id: str, fps: float = 30.0):
        self.media_dir = Path(media_dir)
        self.drone_id = drone_id
        self.fps = fps
        self._writer: cv.VideoWriter | None = None
        self.path: Path | None = None

    @property
    def is_recording(self) -> bool:
        return self._writer is not None

    def start(self, frame) -> Path:
        """Opens the file using the FIRST frame's dimensions - cv2.VideoWriter
        can't change resolution mid-recording, so every later frame passed to
        write() must already match this shape (true as long as the drone
        doesn't change its video resolution mid-flight). Calling start()
        again while already recording is a no-op and returns the existing path."""
        if self.is_recording:
            return self.path
        self.media_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.path = self.media_dir / f"{self.drone_id}_{ts}.mp4"
        height, width = frame.shape[:2]  # numpy shape is (h, w, c) - VideoWriter wants (w, h)
        fourcc = cv.VideoWriter_fourcc(*"mp4v")
        self._writer = cv.VideoWriter(str(self.path), fourcc, self.fps, (width, height))
        return self.path

    def write(self, frame) -> None:
        """No-op if not currently recording - safe to call unconditionally
        from the per-frame hot path."""
        if self._writer is not None:
            self._writer.write(frame)

    def stop(self) -> Path | None:
        """Returns the finished file's path, or None if nothing was recording."""
        if self._writer is not None:
            self._writer.release()
            self._writer = None
        path, self.path = self.path, None
        return path
