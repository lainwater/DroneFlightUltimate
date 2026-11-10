"""capture - save chessboard pictures from a live DFU video source."""

import time
from pathlib import Path

import cv2 as cv

from tools.calibration.camera import Camera

WINDOW = "Calibration capture  (SPACE save, TAB board detection on/off, ESC quit)"


def next_index(folder: Path) -> int:
    """Continue numbering after pictures that are already there."""
    numbers = [int(p.stem.split("_")[-1]) for p in folder.glob("img_*.jpg") if p.stem.split("_")[-1].isdigit()]
    return max(numbers, default=-1) + 1


def find_board(gray, cols: int, rows: int):
    # FAST_CHECK: quickly gives up on frames without a board, so the live view stays smooth
    flags = cv.CALIB_CB_ADAPTIVE_THRESH + cv.CALIB_CB_NORMALIZE_IMAGE + cv.CALIB_CB_FAST_CHECK
    return cv.findChessboardCorners(gray, (cols, rows), flags)


def capture(source: Camera, folder: Path, cols: int, rows: int) -> int:
    """Returns how many pictures were saved."""
    folder.mkdir(parents=True, exist_ok=True)
    index = next_index(folder)
    saved = 0
    detect = True
    last = time.perf_counter()
    print(f"Saving to {folder}  (starting at img_{index:03d}.jpg)")
    try:
        while True:
            frame = source.read()
            display = frame.copy()
            found = False
            if detect:
                gray = cv.cvtColor(frame, cv.COLOR_BGR2GRAY)
                found, corners = find_board(gray, cols, rows)
                if found:
                    cv.drawChessboardCorners(display, (cols, rows), corners, found)
            now = time.perf_counter()
            fps = 1 / (now - last) if now > last else 0
            last = now
            status = "BOARD FOUND" if found else ("no board" if detect else "detection off")
            color = (0, 255, 0) if found else (0, 0, 255)
            cv.putText(display, status, (20, 40), cv.FONT_HERSHEY_SIMPLEX, 1, color, 2)
            info = f"{frame.shape[1]}x{frame.shape[0]}  FPS {fps:.0f}  saved {saved}"
            cv.putText(display, info, (20, 80), cv.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
            cv.imshow(WINDOW, display)

            key = cv.waitKey(1) & 0xFF
            if key == 32:  # SPACE
                path = folder / f"img_{index:03d}.jpg"
                cv.imwrite(str(path), frame)  # the RAW frame, without drawings
                print(f"saved {path.name}" + ("" if found or not detect else "  (no board found in it - calibrate will skip it)"))
                index += 1
                saved += 1
            elif key == 9:  # TAB
                detect = not detect
            elif key in (27, ord("q")):  # ESC / q
                break
    finally:
        cv.destroyWindow(WINDOW)
    return saved
