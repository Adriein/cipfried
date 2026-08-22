import logging
import keyboard
import threading

from cipfried.os import Process, Memory, Video
from cipfried.core import GameState, EngineCommand, Context, FrameBuffer
from cipfried.capture import GameCapture

logger = logging.getLogger(__name__)

class Engine:
    def __init__(self):
        self._state = GameState.Stopped


        self._frame_buffer = FrameBuffer()

        tibia = Process(Memory(), Video())
        self._capture = GameCapture(tibia)

        self.ctx = Context(
            frame_buffer=self._frame_buffer,
            game_state=self._state,
        )


        self._stop_event = threading.Event()
        self._capture_thread: threading.Thread | None = None

    def start(self):
        if self._state != GameState.Stopped:
            logger.warning("Engine is already running or starting.")
            return


        logger.info("Starting cipfried engine...")

        self._capture.wait_for_process()

        self._stop_event.clear()

        self._capture_thread = threading.Thread(
            target=self._capture.capture_loop,
            args=(self._frame_buffer, self._stop_event),
            name="CaptureThread",
            daemon=True
        )

        self._capture_thread.start()

        self._state = GameState.Running
        logger.info("cipfried engine running.")

    def _set_stop_handler(self):
        keyboard.add_hotkey(EngineCommand.Stop.value, self._shutdown)

    def _shutdown(self):
        print(f"The {EngineCommand.Stop.value} key was pressed. Stopping cipfried engine...")
        self._state = GameState.Stopped
