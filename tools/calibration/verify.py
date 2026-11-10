"""verify - original | undistorted side by side, with grid + centre cross."""

from pathlib import Path

import cv2 as cv
import numpy as np

from tools.calibration.calib_io import Undistorter, check_size

WINDOW = "Calibration check  (left original, right undistorted - A: alpha 1/0, ESC quit)"


def draw_grid(img, step: int = 50):
    h, w = img.shape[:2]
    for x in range(0, w, step):
        cv.line(img, (x, 0), (x, h), (255, 0, 0), 1)
    for y in range(0, h, step):
        cv.line(img, (0, y), (w, y), (255, 0, 0), 1)
    cv.line(img, (w // 2, 0), (w // 2, h), (0, 255, 0), 2)
    cv.line(img, (0, h // 2), (w, h // 2), (0, 255, 0), 2)
    return img


def side_by_side(frame, undistorter: Undistorter, step: int = 50):
    """-> one image: original | undistorted (both with grid + labels)."""
    left = draw_grid(frame.copy(), step)
    right = draw_grid(undistorter.apply(frame), step)
    cv.putText(left, "ORIGINAL", (10, 30), cv.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
    cv.putText(right, f"UNDISTORTED  alpha={undistorter.alpha:g}", (10, 30), cv.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
    return np.hstack((left, right))


def handle_key(key: int, undistorter: Undistorter) -> tuple[bool, Undistorter]:
    """-> (quit?, undistorter). A toggles alpha (all pixels <-> cropped)."""
    if key in (27, ord("q")):
        return True, undistorter
    if key in (ord("a"), ord("A")):
        return False, Undistorter(undistorter.calib, 0.0 if undistorter.alpha else 1.0)
    return False, undistorter


def verify_live(source, calib: dict) -> None:
    undistorter = Undistorter(calib, 1.0)
    try:
        while True:
            frame = source.read()
            check_size(calib, frame)
            cv.imshow(WINDOW, side_by_side(frame, undistorter))
            stop, undistorter = handle_key(cv.waitKey(1) & 0xFF, undistorter)
            if stop:
                break
    finally:
        cv.destroyWindow(WINDOW)


def verify_images(files: list[Path], calib: dict) -> None:
    """Step through saved pictures (any key = next, ESC = quit)."""
    undistorter = Undistorter(calib, 1.0)
    try:
        for path in files:
            frame = cv.imread(str(path))
            if frame is None:
                continue
            check_size(calib, frame)
            while True:
                cv.imshow(WINDOW, side_by_side(frame, undistorter))
                key = cv.waitKey(0) & 0xFF
                stop, new = handle_key(key, undistorter)
                if stop:
                    return
                if new is not undistorter:  # alpha toggled - redraw the same picture
                    undistorter = new
                    continue
                break
    finally:
        cv.destroyWindow(WINDOW)
