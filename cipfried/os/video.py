from typing import Optional

import numpy as np
import mss
import threading
import queue

#import pyautogui
from numpy import ndarray


class Video:
    def __init__(self):
        self.stream: VideoStream = VideoStream()
        self._running = False
        self._thread = None

        #screen_width, screen_height = pyautogui.size()
        self.monitor = {
            "top": 0,
            "left": 0,
            "width": 1,
            "height": 1
        }

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._capture_worker, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=1)
            self._thread = None

    def _capture_worker(self):
        with mss.mss() as sct:
            while self._running:
                sct_img = sct.grab(self.monitor)

                frame = np.frombuffer(sct_img.rgb, dtype=np.uint8)
                frame = frame.reshape((sct_img.height, sct_img.width, 3))

                self.stream.put_frame(frame)

    def is_running(self) -> bool:
        return self._running

class VideoStream:
    def __init__(self):
        self._stream: queue.Queue[np.ndarray] = queue.Queue(maxsize=20)

    def put_frame(self, frame: ndarray) -> None:
        try:
            self._stream.put_nowait(frame)
        except queue.Full:
            self._stream.get_nowait()
            self._stream.put_nowait(frame)

    def get_frame(self) -> Optional[np.ndarray]:
        frame = None

        while not self._stream.empty():
            frame = self._stream.get_nowait()

        return frame