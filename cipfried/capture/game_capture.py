import time
import logging
import threading
import numpy as np

from cipfried.os import Process
from cipfried.core import Context
from cipfried.capture import Video

logger = logging.getLogger(__name__)

class GameCapture:
    """Handles hooking to the target game process and streaming frames."""
    def __init__(self, tibia: Process, video: Video):
        self._tibia = tibia
        self._video = video

    def wait_for_process(self, poll_interval: float = 0.5) -> None:
        """Blocks until the target game process is found."""
        self._tibia.hook()
        while self._tibia.pid is None:
            logger.info("Tibia is not running... retrying.")
            time.sleep(poll_interval)
            self._tibia.hook()

        logger.info(f"Hooked to Tibia process (PID: {self._tibia.pid}).")

    def capture_loop(self, ctx: Context, stop_event: threading.Event) -> None:
        """Continuously pulls frames from the video stream and pushes to the frame buffer."""
        self._video.stream_to_buffer(ctx, stop_event)
