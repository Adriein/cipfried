import logging
import keyboard
import threading

from cipfried.core import GameState, EngineCommand, Context, State, FrameBuffer
from cipfried.capture import GameCapture, Video
from cipfried.os import Memory, Process

logger = logging.getLogger(__name__)

class Engine:
    def __init__(self):
        self._state = State()

        self._frame_buffer = FrameBuffer()

        tibia = Process(Memory())
        self._capture = GameCapture(tibia, Video())

        self._ctx = Context(
            frame_buffer=self._frame_buffer,
            game_state=self._state,
        )

        self._stop_event = threading.Event()
        self._capture_thread: threading.Thread | None = None

        self._set_stop_handler()

    def start(self):
        if self._ctx.game_state.current != GameState.Stopped:
            logger.warning("Engine is already running or starting.")
            return


        logger.info("Starting cipfried engine...")

        self._capture.wait_for_process()

        self._stop_event.clear()

        self._capture_thread = threading.Thread(
            target=self._capture.capture_loop,
            args=(self._ctx, self._stop_event),
            name="CaptureThread",
            daemon=True
        )

        self._capture_thread.start()

        self._ctx.game_state.current = GameState.Running
        logger.info("cipfried engine running.")

    def _set_stop_handler(self):
        keyboard.add_hotkey(EngineCommand.Stop.value, self._shutdown)

    def _shutdown(self):
        logger.info("Hotkey %s pressed.", EngineCommand.Stop.value)

        if self._ctx.game_state.current == GameState.Stopped:
            return

        logger.info("Stopping cipfried engine...")

        self._stop_event.set()

        if self._capture_thread and self._capture_thread.is_alive():
            self._capture_thread.join(timeout=3.0)

        self._ctx.game_state.current = GameState.Stopped

        logger.info("cipfried engine stopped.")
