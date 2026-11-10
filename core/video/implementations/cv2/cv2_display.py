"""
CV2Display - Output frames to cv2 window from Bus
"""

import asyncio
import time
from datetime import datetime
from pathlib import Path

import cv2 as cv

from core.video.base import VideoBase
from core.video.calibration import CameraCalibration, load_calibration
from core.video.implementations.cv2.vision import ArucoMarkerDetector, Undistorter

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
ARUCO_COLOR = (255, 0, 255)  # BGR magenta - marker outlines + ArUco status line
UNDISTORT_COLOR = (255, 255, 0)  # BGR cyan - undistort status line
AXIS_COLORS = ((0, 0, 255), (0, 255, 0), (255, 0, 0))  # x red, y green, z blue (like cv.drawFrameAxes)


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

        # --- camera calibration (undistort + ArUco pose) ---
        # get_videostream(..., calibration="tello") - name of core/video/calibration/<name>.npz
        self.calibration_name: str | None = kwargs.get("calibration")
        self._calibration: CameraCalibration | None = None
        self.is_undistorting = False
        self._undistorter: Undistorter | None = None
        self._undistort_note: str | None = None  # why undistort is not applied right now (size mismatch)

        # --- ArUco state (defaults overridable via get_videostream kwargs) ---
        self.aruco_dictionary: str = kwargs.get("aruco_dictionary", "DICT_5X5_50")
        self.aruco_marker_size: float = float(kwargs.get("aruco_marker_size", 0.15))  # metres, black square edge
        self.aruco_publish: bool = bool(kwargs.get("aruco_publish", False))
        self.is_aruco_detecting = False
        self._aruco: ArucoMarkerDetector | None = None
        self._aruco_task: asyncio.Task | None = None
        self._markers: list[dict] = []
        self._aruco_ms = None
        self._aruco_note: str | None = None  # e.g. "no calibration - no pose"

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
        if self.is_aruco_detecting:
            await self.stop_aruco()
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
            self._markers = []
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
        for det in self._detections:
            x1, y1, x2, y2 = (round(v * box_scale) for v in det["box"])
            cv.rectangle(frame, (x1, y1), (x2, y2), BOX_COLOR, thick)
            label = f"{det['label']} {det['conf']:.2f}"
            cv.putText(frame, label, (x1, max(round(15 * ui), y1 - round(8 * ui))), cv.FONT_HERSHEY_SIMPLEX, font, BOX_COLOR, thick)

    # ------------------------------------------------------------ calibration / undistort

    def _get_calibration(self, name: str | None = None) -> CameraCalibration:
        """Load (and cache) the calibration. `name` overrides the one given at creation."""
        name = name or self.calibration_name
        if name is None:
            raise ValueError("No camera calibration set - pass calibration='tello' (or 'webcam', ...) to get_videostream()")
        if self._calibration is None or self._calibration.name != name:
            self._calibration = load_calibration(name)
            self.calibration_name = self._calibration.name
            self._undistorter = None
        return self._calibration

    async def undistort_on(self, calibration: str | None = None, alpha: float = 1.0) -> None:
        """Show the undistorted image (remove lens distortion).
        calibration - name in core/video/calibration (default: the one given at creation)
        alpha       - 1.0 keep all pixels (black curved borders), 0.0 crop to valid area"""
        try:
            calib = self._get_calibration(calibration)
        except (ValueError, FileNotFoundError) as e:
            await self._publish_parser("error", {"error": type(e).__name__, "message": str(e)})
            return
        self._undistorter = Undistorter(calib, alpha)
        self.is_undistorting = True
        self._detections, self._markers = [], []  # old results are in the other geometry
        await self._publish_parser("ack", {"cmd": "undistort_on", "ack": "True", "calibration": calib.name})

    async def undistort_off(self) -> None:
        self.is_undistorting = False
        self._undistort_note = None
        self._detections, self._markers = [], []
        await self._publish_parser("ack", {"cmd": "undistort_off", "ack": "True"})

    def _undistort(self, frame):
        """-> (frame to process + display, camera matrix, distortion) for that frame.
        Camera parameters are None when there is no fitting calibration."""
        calib = self._calibration
        if calib is None and self.calibration_name and (self.is_aruco_detecting or self.is_undistorting):
            try:
                calib = self._get_calibration()
            except (ValueError, FileNotFoundError):
                self.calibration_name = None  # error was already reported - don't retry on every frame
                calib = None
        if calib is None:
            return frame, None, None
        if not calib.matches(frame.shape):
            self._undistort_note = calib.mismatch_text(frame.shape)
            return frame, None, None
        self._undistort_note = None
        if self.is_undistorting and self._undistorter is not None:
            frame = self._undistorter.apply(frame)
            return frame, self._undistorter.new_camera_matrix, None  # undistorted image: no distortion left
        return frame, calib.camera_matrix, calib.dist_coeffs

    # ------------------------------------------------------------ ArUco

    async def start_aruco(
        self, dictionary: str | None = None, marker_size: float | None = None, publish: bool | None = None, calibration: str | None = None
    ) -> None:
        """Detect ArUco markers and draw them; with a calibration also localize
        them (x, y, z, distance, roll/pitch/yaw relative to the camera).

        dictionary  - e.g. "DICT_5X5_50" (default from creation, see __init__)
        marker_size - black square edge in METRES - wrong size = wrong distance!
        publish     - publish every result on data.stream.{drone_id} as {"aruco": [...]}
        calibration - calibration name, default: the one given at creation

        Same worker pattern as YOLO: one frame at a time in a thread, frames
        arriving meanwhile are shown with the last known markers."""
        if self.is_aruco_detecting:
            await self._publish_parser("ack", {"cmd": "start_aruco", "ack": "already_running"})
            return
        try:
            self._aruco = ArucoMarkerDetector(dictionary or self.aruco_dictionary, marker_size or self.aruco_marker_size)
        except Exception as e:
            await self._publish_parser("error", {"error": type(e).__name__, "message": str(e)})
            return
        if publish is not None:
            self.aruco_publish = bool(publish)
        self._aruco_note = None
        try:
            self._get_calibration(calibration)
        except (ValueError, FileNotFoundError) as e:
            self._aruco_note = "no calibration - detect only, no pose"
            await self._publish_parser("error", {"error": type(e).__name__, "message": f"{e} - ArUco runs without pose."})
        self._markers = []
        self._aruco_ms = None
        self.is_aruco_detecting = True
        await self._publish_parser(
            "ack",
            {
                "cmd": "start_aruco",
                "ack": "True",
                "dictionary": self._aruco.dictionary_name,
                "marker_size": self._aruco.marker_size,
                "calibration": self._calibration.name if self._calibration else None,
            },
        )

    async def stop_aruco(self) -> None:
        self.is_aruco_detecting = False
        task, self._aruco_task = self._aruco_task, None
        if task is not None:
            try:
                await task
            except Exception:
                pass
        self._markers = []
        await self._publish_parser("ack", {"cmd": "stop_aruco", "ack": "True"})

    def _maybe_submit_aruco(self, frame, camera_matrix, dist_coeffs) -> None:
        if not self.is_aruco_detecting or self._aruco is None:
            return
        if self._aruco_task is None or self._aruco_task.done():
            self._aruco_task = asyncio.create_task(self._run_aruco(frame.copy(), camera_matrix, dist_coeffs))

    async def _run_aruco(self, frame, camera_matrix, dist_coeffs) -> None:
        try:
            t0 = time.perf_counter()
            markers = await asyncio.to_thread(self._aruco.detect, frame, camera_matrix, dist_coeffs)
            self._aruco_ms = (time.perf_counter() - t0) * 1000
        except Exception as e:
            self.is_aruco_detecting = False
            self._markers = []
            await self._publish_parser("error", {"error": type(e).__name__, "message": f"ArUco failed, stopped: {e}"})
            return
        if not self.is_aruco_detecting:
            return
        self._markers = markers
        if self.aruco_publish:
            await self._publish_parser("data", {"aruco": [{k: v for k, v in m.items() if k != "axes"} for m in markers]})

    def _draw_markers(self, frame, box_scale: float = 1.0, ui: float = 1.0) -> None:
        thick = max(1, round(2 * ui))
        font = 0.6 * ui
        for m in self._markers:
            pts = [(round(x * box_scale), round(y * box_scale)) for x, y in m["corners"]]
            for i in range(4):
                cv.line(frame, pts[i], pts[(i + 1) % 4], ARUCO_COLOR, thick)
            if "axes" in m:
                origin, *ends = [(round(x * box_scale), round(y * box_scale)) for x, y in m["axes"]]
                for end, color in zip(ends, AXIS_COLORS):
                    cv.line(frame, origin, end, color, thick)
                label = f"ID {m['id']}  {m['distance']:.2f} m"
            else:
                label = f"ID {m['id']}"
            x, y = pts[0]
            cv.putText(frame, label, (x, max(round(15 * ui), y - round(8 * ui))), cv.FONT_HERSHEY_SIMPLEX, font, ARUCO_COLOR, thick)

    def _draw_status_lines(self, frame, ui: float = 1.0) -> None:
        """Bottom-left: one line per running feature - proves it runs even when nothing is found."""
        lines = []
        if self.is_object_detecting:
            text = "YOLO: waiting for first result..." if self._det_ms is None else f"YOLO: {len(self._detections)} obj, {self._det_ms:.0f} ms"
            lines.append((text, BOX_COLOR))
        if self.is_aruco_detecting:
            if self._aruco_ms is None:
                text = "ArUco: waiting for first result..."
            else:
                text = f"ArUco {self._aruco.dictionary_name}: {len(self._markers)} marker, {self._aruco_ms:.0f} ms"
            note = self._aruco_note or (self._undistort_note and "no pose: " + self._undistort_note)
            if note:
                text += f"  ({note})"
            lines.append((text, ARUCO_COLOR))
        if self.is_undistorting:
            text = f"UNDISTORTED ({self.calibration_name})" if not self._undistort_note else f"undistort paused: {self._undistort_note}"
            lines.append((text, UNDISTORT_COLOR))
        font = 0.6 * ui
        thick = max(1, round(2 * ui))
        for i, (text, color) in enumerate(reversed(lines)):
            y = frame.shape[0] - round(20 * ui) - i * round(28 * ui)
            cv.putText(frame, text, (round(20 * ui), y), cv.FONT_HERSHEY_SIMPLEX, font, color, thick)

    # ------------------------------------------------------------ frames
    async def _update_frame(self, data):
        """Update displayed frame"""
        ts_fps_new = datetime.timestamp(datetime.now())
        frame = await self._data_to_frame(data)
        self._reset_window_if_resized(frame)
        # recordings + snapshots keep the RAW camera image (a calibration can be redone later)
        self._latest_frame = frame.copy()
        if self.recorder.is_recording:
            self.recorder.write(self._latest_frame)

        # undistort (if on and the calibration fits this camera/resolution); YOLO and
        # ArUco run on the same image that is displayed, so boxes/markers line up
        frame, camera_matrix, dist_coeffs = self._undistort(frame)
        self._maybe_submit_detection(frame)
        self._maybe_submit_aruco(frame, camera_matrix, dist_coeffs)

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
        self._draw_markers(frame, box_scale, ui)
        self._draw_status_lines(frame, ui)

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
                            frame,
                            text=f"{item}: {self._format_value(self.state_data[item])}",
                            position=pos,
                            font_scale=font_scale,
                            thickness=thickness,
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
