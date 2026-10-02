"""
save_snapshot - write a single frame to disk as a .jpg. Stateless,
single-shot - used by VideoBase.take_snapshot().
"""

from datetime import datetime
from pathlib import Path

import cv2 as cv


def save_snapshot(frame, media_dir: Path, drone_id: str) -> Path:
    media_dir = Path(media_dir)
    media_dir.mkdir(parents=True, exist_ok=True)
    # microsecond precision so two snapshots taken in the same second
    # (e.g. mashing the key) don't silently overwrite each other
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S-%f")[:-3]
    path = media_dir / f"{drone_id}_{ts}.jpg"
    cv.imwrite(str(path), frame)
    return path
