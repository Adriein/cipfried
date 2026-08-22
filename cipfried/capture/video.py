import logging
import threading
import time

import numpy as np

from fastgrab import screenshot as fb

from cipfried.core import Context

logger = logging.getLogger(__name__)


class Video:
    """Wayland high-performance video capture using fastgrab."""

    def __init__(self, output_name: str | None = None, fps_target: int = 60):
        self._output_name = output_name
        self._target_frame_time = 1.0 / fps_target if fps_target > 0 else 0.0
        self._grabber = fb.Screenshot()



    def stream_to_buffer(self, ctx: Context, stop_event: threading.Event) -> None:
        logger.info("[Video Capture Thread] Loop started.")
        last_capture_time = 0.0

        if self._grabber is None:
            logger.info("[Video Capture Thread] Initializing fastgrab...")
            self._grabber = fb.Screenshot()

        try:
            while not stop_event.is_set():
                now = time.perf_counter()

                elapsed = now - last_capture_time
                if elapsed < self._target_frame_time:
                    time.sleep(self._target_frame_time - elapsed)
                    continue

                frame: np.ndarray = self._grabber.capture()
                last_capture_time = time.perf_counter()

                if frame is not None and frame.size > 0:
                    ctx.frame_buffer.push(frame)

        except Exception as e:
            logger.error(f"[Video Capture Thread] Error during capture stream: {e}")
        finally:
            self.close()
            logger.info("[Video Capture Thread] Loop exited.")

    def close(self) -> None:
        self._grabber = None
        logger.info("[Video Capture Thread] FastGrab resources released.")