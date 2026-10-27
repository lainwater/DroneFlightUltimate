"""
CV2Display - Output frames to cv2 window from Bus
"""

import asyncio
import time
from datetime import datetime
from pathlib import Path

import cv2 as cv

from core.video.base import VideoBase

TEXT_SPACING = 40

# YOLO model: looked up next to this file first (video/implementations/cv2/),
# then one level up (video/). If neither exists the bare name is handed to
# ultralytics, which downloads it automatically.
DEFAULT_MODEL_NAME = "yolo26n.pt"
BOX_COLOR = (0, 255, 0)  # BGR


class CV2Display(VideoBase):
    def __init__(self, drone_id: str, bus: object, **kwargs):
        super().__init__(drone_id, bus, **kwargs)
        self.cap = None
        self.ts_fps_old = datetime.timestamp(datetime.now())

        # --- object detection state ---
        self.is_object_detecting = False
        self._model = None
        self._det_task: asyncio.Task | None = None
        self._detections: list[dict] = []  # latest result, drawn on every frame
        self._det_conf = 0.4
        self._det_imgsz = 640
        self._det_classes: list[int] | None = None
        self._det_publish = False
        self._det_ms = None  # last inference time, shown in the status line
        self._model_path = None

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
        if self.is_object_detecting:
            await self.stop_detection()
        cv.destroyWindow(self.drone_id)
        self._detach()
        self.is_running = False

    # ------------------------------------------------------------ detection

    # async def _publish_detect_parser(self, data: dict) -> None:
    #     """Publish to the bus."""
    #     if self.bus:
    #         await self.bus.publish(f"project.{self.drone_id}", data)

    @staticmethod
    def _resolve_model_path(model_path: str | Path | None) -> str:
        if model_path:
            return str(model_path)
        here = Path(__file__).parent
        folders = (here, here.parent.parent)
        for folder in folders:
            if (folder / DEFAULT_MODEL_NAME).exists():
                return str(folder / DEFAULT_MODEL_NAME)
        # not the default name (e.g. yolo26.pt) - take any yolo*.pt that is there
        for folder in folders:
            found = sorted(folder.glob("yolo*.pt"))
            if found:
                return str(found[0])
        return DEFAULT_MODEL_NAME  # ultralytics tries to download it (needs internet!)

    async def start_detection(
        self,
        model_path: str | Path | None = None,
        conf: float = 0.4,
        imgsz: int = 640,
        classes: list[int] | None = None,
        publish: bool = False,
    ) -> None:
        """Run YOLO on the frames received from the bus and draw boxes
        on the displayed frame.

        conf     - minimum confidence
        imgsz    - inference size (smaller = faster)
        classes  - only detect these class ids (e.g. [0] = person), None = all
        publish  - also publish each result as data.stream.{drone_id}
                   (off by default - it would flood a live logger)

        Inference runs in a worker thread and only ONE frame at a time is
        processed; frames that arrive while it is busy are displayed
        normally (with the last known boxes) and skipped for detection,
        so the video never stalls.
        """
        if self.is_object_detecting:
            await self._publish_parser("ack", {"cmd": "start_detection", "ack": "already_running"})
            return

        self._det_conf = conf
        self._det_imgsz = imgsz
        self._det_classes = classes
        self._det_publish = publish

        if self._model is None:
            path = self._resolve_model_path(model_path)
            self._model_path = path
            try:
                self._model = await asyncio.to_thread(self._load_model, path)
            except Exception as e:
                await self._publish_parser("error", {"error": type(e).__name__, "message": f"Could not load YOLO model '{path}': {e}"})
                return

        self._detections = []
        self._det_ms = None
        self.is_object_detecting = True
        await self._publish_parser("ack", {"cmd": "start_detection", "ack": "True", "model": self._model_path})

    async def stop_detection(self) -> None:
        """Stop detection, wait for an inference that is still running
        (a thread can't be cancelled), and clear the boxes."""
        self.is_object_detecting = False
        task, self._det_task = self._det_task, None
        if task is not None:
            try:
                await task
            except Exception:
                pass
        self._detections = []
        await self._publish_parser("ack", {"cmd": "stop_detection", "ack": "True"})

    @staticmethod
    def _load_model(path: str):
        try:
            from ultralytics import YOLO  # imported lazily: slow import, only needed when detecting
        except ModuleNotFoundError as e:
            import sys

            raise ModuleNotFoundError(
                f'{e} - this program runs on {sys.executable}; install into THAT interpreter: "{sys.executable}" -m pip install ultralytics'
            ) from e

        return YOLO(path)

    def _infer(self, frame) -> list[dict]:
        """Blocking - always called through asyncio.to_thread()."""
        results = self._model(frame, conf=self._det_conf, imgsz=self._det_imgsz, classes=self._det_classes, verbose=False)
        boxes = results[0].boxes
        out = []
        for (x1, y1, x2, y2), score, cls in zip(boxes.xyxy.tolist(), boxes.conf.tolist(), boxes.cls.tolist()):
            out.append(
                {
                    "label": self._model.names[int(cls)],
                    "class_id": int(cls),
                    "conf": float(score),
                    "box": (int(x1), int(y1), int(x2), int(y2)),
                }
            )
        return out

    async def _run_detection(self, frame) -> None:
        try:
            t0 = time.perf_counter()
            detections = await asyncio.to_thread(self._infer, frame)
            self._det_ms = (time.perf_counter() - t0) * 1000
        except Exception as e:
            # Don't spam an error on every frame - switch detection off.
            self.is_object_detecting = False
            self._detections = []
            await self._publish_parser("error", {"error": type(e).__name__, "message": f"Detection failed, stopped: {e}"})
            return
        if not self.is_object_detecting:  # stopped while this one was running
            return
        self._detections = detections
        if self._det_publish:
            await self._publish_parser("data", {"detections": detections})

    def _maybe_submit_detection(self, frame) -> None:
        """Hand the raw frame to the worker, unless it is still busy."""
        if not self.is_object_detecting:
            return
        if self._det_task is None or self._det_task.done():
            self._det_task = asyncio.create_task(self._run_detection(frame.copy()))

    def _draw_detections(self, frame) -> None:
        if self.is_object_detecting:
            # status line: proves detection is running even when nothing is found
            if self._det_ms is None:
                status = "YOLO: waiting for first result..."
            else:
                status = f"YOLO: {len(self._detections)} obj, {self._det_ms:.0f} ms"
            cv.putText(frame, status, (20, frame.shape[0] - 20), cv.FONT_HERSHEY_SIMPLEX, 0.6, BOX_COLOR, 2)
        for det in self._detections:
            x1, y1, x2, y2 = det["box"]
            cv.rectangle(frame, (x1, y1), (x2, y2), BOX_COLOR, 2)
            label = f"{det['label']} {det['conf']:.2f}"
            cv.putText(frame, label, (x1, max(15, y1 - 8)), cv.FONT_HERSHEY_SIMPLEX, 0.6, BOX_COLOR, 2)

    # ------------------------------------------------------------ frames
    async def _update_frame(self, data):
        """Update displayed frame"""
        ts_fps_new = datetime.timestamp(datetime.now())
        frame = await self._data_to_frame(data)
        self._latest_frame = frame.copy()
        if self.recorder.is_recording:
            self.recorder.write(self._latest_frame)

        # detection runs on the raw frame; boxes are drawn on the display copy
        self._maybe_submit_detection(self._latest_frame)
        self._draw_detections(frame)

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
