import time
import logging
import threading
import numpy as np

from cipfried.os import Process
from cipfried.core import FrameBuffer

logger = logging.getLogger(__name__)

class GameCapture:
    """Handles hooking to the target game process and streaming frames."""
    def __init__(self, tibia: Process):
        self._tibia = tibia

    def wait_for_process(self, poll_interval: float = 0.5) -> None:
        """Blocks until the target game process is found."""
        self._tibia.hook()
        while self._tibia.pid is None:
            logger.info("Tibia is not running... retrying.")
            time.sleep(poll_interval)
            self._tibia.hook()

        logger.info(f"Hooked to Tibia process (PID: {self._tibia.pid}).")

    def capture_loop(self, frame_buffer: FrameBuffer, stop_event: threading.Event) -> None:
        """Continuously pulls frames from the video stream and pushes to the frame buffer."""
        video_stream = self._tibia.capture_video_stream()

        # If capture_video() returns an iterator/generator or yields frames:
        while not stop_event.is_set():
            frame = video_stream.read()  # Adjust based on your Video API signature
            if frame is not None:
                frame_buffer.push(frame)
            else:
                time.sleep(0.001)  # Prevent CPU spinning if frame is empty