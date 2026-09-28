"""
public API of core.video.
"""

from enum import Enum

from .base import VideoBase


class VideoOutputType(Enum):
    CV2 = "cv2"
    WEBSERVER = "web_server"


def get_videostream(_type: VideoOutputType, drone_id: str, bus: object, **kwargs) -> VideoBase:
    """Returns a video stream object"""
    match _type:
        case VideoOutputType.CV2:
            from core.video.implementations.cv2.cv2_display import CV2Display

            return CV2Display(drone_id, bus, **kwargs)
        case VideoOutputType.WEBSERVER:
            raise NotImplementedError
            from core.video.implementations.web_server.web_server import WebServerDisplay

            return WebServerDisplay(drone_id, bus, kwargs)


__all__ = ["VideoBase", "get_videostream", "VideoOutputType"]
