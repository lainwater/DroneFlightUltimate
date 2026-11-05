"""
CV2Display - Output frames to cv2 window from Bus
"""

import asyncio
import math
import time
from datetime import datetime
from pathlib import Path

import cv2 as cv

from core.video.base import VideoBase

TEXT_SPACING = 40  # at UI_REF_HEIGHT, scaled with the displayed frame height
UI_REF_HEIGHT = 720  # overlay text/boxes are designed for a frame this tall

# Frames are fitted into this box (aspect ratio kept): big input is shrunk,
# small input (e.g. the 320x240 downward camera) is enlarged.
DISPLAY_TARGET_SIZE = (960, 720)  # (width, height)

# YOLO model: looked up next to this file first (video/implementations/cv2/),
# then one level up (video/). If neither exists the bare name is handed to
# ultralytics, which downloads it automatically.
DEFAULT_MODEL_NAME = "yolo26n.pt"
BOX_COLOR = (0, 255, 0)  # BGR
CUSTOM_TEXT_COLOR = (0, 255, 255)  # BGR yellow - custom data block (top-right)


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
        self._last_shape = None  # frame shape the window was sized for
        self.auto_fit = True
        self.target_size = DISPLAY_TARGET_SIZE
        self._pump_task: asyncio.Task | None = None

    @property
    def config_dir(self) -> Path:
        return Path(__file__).parent

    async def start_stream(self):
        """Start the video stream."""
        self._attach()
        cv.namedWindow(self.drone_id)
        self.is_running = True
        self._pump_task = asyncio.create_task(self._pump_window())

    async def stop_stream(self):
        """Stop the video stream."""
        if self.is_object_detecting:
            await self.stop_detection()
        if self._pump_task is not None:
            self._pump_task.cancel()
            self._pump_task = None
        cv.destroyWindow(self.drone_id)
        self._detach()
        self.is_running = False

    async def _pump_window(self) -> None:
        """waitKey() is what lets the GUI process its events. It used to run only
        when a frame arrived, so a gap in the video (camera switch) made the
        window show '(Not Responding)'."""
        while True:
            cv.waitKey(1)
            await asyncio.sleep(0.03)

    def _reset_window_if_resized(self, frame) -> None:
        """Forward and downward camera have different resolutions - recreate
        the window so it fits the new size, and drop boxes of the old one."""
        if self._last_shape is not None and frame.shape != self._last_shape:
            cv.destroyWindow(self.drone_id)
            cv.namedWindow(self.drone_id)
            self._detections = []
        self._last_shape = frame.shape

    # ------------------------------------------------------------ detection

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

    def _draw_detections(self, frame, box_scale: float = 1.0, ui: float = 1.0) -> None:
        """box_scale: raw frame -> displayed frame (boxes come in raw coordinates).
        ui: overlay size factor (line width, font size)."""
        font = 0.6 * ui
        thick = max(1, round(2 * ui))
        if self.is_object_detecting:
            # status line: proves detection is running even when nothing is found
            if self._det_ms is None:
                status = "YOLO: waiting for first result..."
            else:
                status = f"YOLO: {len(self._detections)} obj, {self._det_ms:.0f} ms"
            cv.putText(frame, status, (round(20 * ui), frame.shape[0] - round(20 * ui)), cv.FONT_HERSHEY_SIMPLEX, font, BOX_COLOR, thick)
        for det in self._detections:
            x1, y1, x2, y2 = (round(v * box_scale) for v in det["box"])
            cv.rectangle(frame, (x1, y1), (x2, y2), BOX_COLOR, thick)
            label = f"{det['label']} {det['conf']:.2f}"
            cv.putText(frame, label, (x1, max(round(15 * ui), y1 - round(8 * ui))), cv.FONT_HERSHEY_SIMPLEX, font, BOX_COLOR, thick)

    # ------------------------------------------------------------ frames
    async def _update_frame(self, data):
        """Update displayed frame"""
        ts_fps_new = datetime.timestamp(datetime.now())
        frame = await self._data_to_frame(data)
        self._reset_window_if_resized(frame)
        self._latest_frame = frame.copy()
        if self.recorder.is_recording:
            self.recorder.write(self._latest_frame)

        # detection runs on the raw frame; boxes are drawn on the display copy
        self._maybe_submit_detection(self._latest_frame)

        # 1) bring the frame to display size (auto-fit * manual rescale_factor) BEFORE
        #    drawing, so text and boxes are rendered crisp at the final size
        raw_w = frame.shape[1]
        scale = self._fit_scale(frame) * self.rescale_factor
        if scale != 1:
            frame = await self._rescale_frame(frame, scale)
        box_scale = frame.shape[1] / raw_w

        # 2) overlay sized relative to the displayed frame height
        ui = frame.shape[0] / UI_REF_HEIGHT
        spacing = round(TEXT_SPACING * ui)
        font_scale = 1.0 * ui
        thickness = max(1, round(2 * ui))

        self._draw_detections(frame, box_scale, ui)

        await self._display_text(frame, text=self.drone_id, position=(round(30 * ui), round(50 * ui)), font_scale=font_scale, thickness=thickness)
        if self.display_state_data:
            i = 0
            for item in self.data_to_display:
                i += 1
                pos = (round(20 * ui), round(80 * ui) + i * spacing)
                if item == "ts" or item == "timestamp":
                    await self._display_text(frame, text=f"{self.ts}", position=pos, font_scale=font_scale, thickness=thickness)
                elif item == "fps":
                    delta = float(ts_fps_new) - float(self.ts_fps_old)
                    fps = 1 / delta if delta > 0 else 0.0
                    await self._display_text(frame, text=f"FPS: {fps:.1f}", position=pos, font_scale=font_scale, thickness=thickness)
                    self.ts_fps_old = ts_fps_new
                else:
                    try:
                        await self._display_text(
                            frame, text=f"{item}: {self.state_data[item]}", position=pos, font_scale=font_scale, thickness=thickness
                        )
                    except (KeyError, TypeError):
                        pass

        if self.display_custom_data and self.custom_data:
            self._draw_custom_data(frame, ui)

        if self.fpv_goggles_mode:
            frame = await self._to_fpv_goggles_frame(frame)

        cv.imshow(self.drone_id, frame)
        cv.waitKey(1)

    def _draw_custom_data(self, frame, ui: float = 1.0) -> None:
        """Second data block (sent by the project via display.{drone_id}),
        top-right on a dark background so it stays readable on any image."""
        lines = self._custom_data_lines()
        if not lines:
            return
        font = cv.FONT_HERSHEY_SIMPLEX
        font_scale = 0.6 * ui
        thickness = max(1, round(1.5 * ui))
        (_, text_h), _ = cv.getTextSize("Ag", font, font_scale, thickness)
        line_h = round(text_h * 1.8)
        width = max(cv.getTextSize(line, font, font_scale, thickness)[0][0] for line in lines)
        margin = round(10 * ui)
        x = max(0, frame.shape[1] - width - 2 * margin - round(10 * ui))
        y = round(20 * ui)
        x2 = min(frame.shape[1], x + width + 2 * margin)
        y2 = min(frame.shape[0], y + line_h * len(lines) + margin)
        roi = frame[y:y2, x:x2]
        roi[:] = (roi * 0.4).astype(roi.dtype)  # darken behind the text
        for i, line in enumerate(lines):
            cv.putText(frame, line, (x + margin, y + margin + text_h + i * line_h), font, font_scale, CUSTOM_TEXT_COLOR, thickness, cv.LINE_AA)

    def _fit_scale(self, frame) -> float:
        """Scale that fits the frame into target_size with the aspect ratio kept
        (shrinks big frames, enlarges small ones). 1.0 when auto_fit is off."""
        if not self.auto_fit:
            return 1.0
        h, w = frame.shape[:2]
        tw, th = self.target_size
        return min(tw / w, th / h)

    async def set_display_size(self, width: int = 960, height: int = 720):
        """Box (px) the video is fitted into, aspect ratio is kept."""
        self.target_size = (int(width), int(height))
        self.auto_fit = True

    async def set_auto_fit(self, enabled: bool = True):
        """Turn fitting to target_size on/off (off = show the native resolution)."""
        self.auto_fit = bool(enabled)

    async def _rescale_frame(self, frame, scale):
        width = max(1, round(frame.shape[1] * scale))
        height = max(1, round(frame.shape[0] * scale))
        interp = cv.INTER_AREA if scale < 1 else cv.INTER_LINEAR
        return cv.resize(frame, (width, height), interpolation=interp)

    async def _to_fpv_goggles_frame(self, frame):
        h, w = frame.shape[:2]
        side = min(h, w)
        x0 = (w - side) // 2
        y0 = (h - side) // 2
        square = frame[y0 : y0 + side, x0 : x0 + side]
        return cv.hconcat([square, square])

    async def _display_text(self, frame, text=None, position=(30, 50), font=cv.FONT_HERSHEY_SIMPLEX, font_scale=1, color=(255, 0, 115), thickness=2):
        """Render text on frame"""
        cv.putText(frame, str(text), position, font, font_scale, color, thickness)

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
