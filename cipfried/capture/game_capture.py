import time
import logging
from typing import Generator
import numpy as np

from cipfried.os import Process, Memory, Video

logger = logging.getLogger(__name__)

class GameCapture:
    """Handles hooking to the target game process and streaming frames."""
    def __init__(self):
        self._process = Process(Memory(), Video())

    def wait_for_process(self, poll_interval: float = 0.5) -> None:
        """Blocks until the target game process is found."""
        self._process.hook()
        while self._process.pid is None:
            logger.info("Tibia is not running... retrying.")
            time.sleep(poll_interval)
            self._process.hook()

        logger.info(f"Hooked to Tibia process (PID: {self._process.pid}).")

    def capture_loop(self, frame_buffer, stop_event) -> None:
        """Continuously pulls frames from the video stream and pushes to the frame buffer."""
        video_stream = self._process.capture_video()

        # If capture_video() returns an iterator/generator or yields frames:
        while not stop_event.is_set():
            frame = video_stream.read()  # Adjust based on your Video API signature
            if frame is not None:
                frame_buffer.push(frame)
            else:
                time.sleep(0.001)  # Prevent CPU spinning if frame is empty