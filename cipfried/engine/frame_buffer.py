import threading
import numpy as np
import time

class LatestFrameBuffer:
    def __init__(self):
        self._frame = None
        self._timestamp = 0.0
        self._lock = threading.Lock()

    def push(self, frame: np.ndarray):
        """Called by the Screen Capture Thread non-stop."""
        with self._lock:
            self._frame = frame
            self._timestamp = time.perf_counter()

    def get_latest(self):
        """Called by Bot Vision Threads whenever they are ready to process."""
        with self._lock:
            if self._frame is None:
                return None, 0.0
            # Return a fast reference/copy of the latest frame
            return self._frame, self._timestamp