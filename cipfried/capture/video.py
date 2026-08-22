import logging
import threading
import time

import numpy as np

from fastgrab import FastGrab

from cipfried.core import Context

logger = logging.getLogger(__name__)


class Video:
    """Wayland high-performance video capture using fastgrab[wayland].

    Hooks into wlr-screencopy-v1 via pywayland to write zero-copy
    NumPy arrays directly into the shared Context frame buffer.
    """

    def __init__(self, output_name: str | None = None, fps_target: int = 60):
        """
        :param output_name: Specific Wayland output display (e.g. 'DP-1', 'HDMI-A-1').
                            If None, fastgrab picks the primary display.
        :param fps_target: Target capture frequency limit to prevent unnecessary CPU usage.
        """
        self._output_name = output_name
        self._target_frame_time = 1.0 / fps_target if fps_target > 0 else 0.0
        self._grabber: FastGrab | None = None

    def _initialize_grabber(self) -> None:
        """Instantiates the fastgrab Wayland instance."""
        try:
            logger.info("Initializing fastgrab [wayland / wlr-screencopy]...")
            if self._output_name:
                self._grabber = FastGrab(backend="wayland", output=self._output_name)
            else:
                self._grabber = FastGrab(backend="wayland")
            logger.info("FastGrab Wayland instance initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize fastgrab[wayland]: {e}")
            raise e

    def stream_to_buffer(self, ctx: Context, stop_event: threading.Event) -> None:
        """Target worker method run inside the capture thread.

        Continuously reads frames from fastgrab and updates ctx.frame_buffer.

        :param ctx: The shared application Context object containing frame_buffer and state.
        :param stop_event: Threading event to signal graceful loop exit.
        """
        if self._grabber is None:
            self._initialize_grabber()

        logger.info("[Video Capture Thread] Loop started.")

        last_capture_time = 0.0

        try:
            while not stop_event.is_set():
                now = time.perf_counter()

                # Optional frame pacing (if target FPS set)
                elapsed = now - last_capture_time
                if elapsed < self._target_frame_time:
                    time.sleep(self._target_frame_time - elapsed)
                    continue

                # 1. Grab raw frame (Returns zero-copy NumPy array in BGR/RGB)
                frame: np.ndarray = self._grabber.capture()
                last_capture_time = time.perf_counter()

                if frame is not None and frame.size > 0:
                    # 2. Push directly into the thread-safe buffer
                    ctx.frame_buffer.push(frame)

        except Exception as e:
            logger.error(f"[Video Capture Thread] Error during capture stream: {e}")
        finally:
            self.close()
            logger.info("[Video Capture Thread] Loop exited.")

    def close(self) -> None:
        """Releases Wayland screen descriptors and cleans up fastgrab allocation."""
        if self._grabber is not None:
            try:
                # Release internal pywayland buffers
                if hasattr(self._grabber, "close"):
                    self._grabber.close()
            except Exception as e:
                logger.warning(f"Error while closing FastGrab handle: {e}")
            finally:
                self._grabber = None
                logger.info("FastGrab resources released.")