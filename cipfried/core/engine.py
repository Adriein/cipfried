import logging
import keyboard
import threading
import time

from cipfried.core.constants import EngineCommand, GameState
from cipfried.core.context import Context, State
from cipfried.os.memory import Memory
from cipfried.os.process import Process

logger = logging.getLogger(__name__)

class Engine:
    def __init__(self):
        self._state = State()

        self._process = Process(Memory())

        self._ctx = Context(
            game_state=self._state,
        )

        self._stop_event = threading.Event()

        self._set_stop_handler()

    def start(self):
        if self._ctx.game_state.current != GameState.Stopped:
            logger.warning("Engine is already running or starting.")
            return

        self._stop_event.clear()
        self._ctx.game_state.current = GameState.Running

        logger.info("Starting cipfried engine...")

        self._wait_for_process()

        if not self._stop_event.is_set():
            logger.info("cipfried engine running (PID: %s).", self._process.pid)
            self._stop_event.wait()

        self._ctx.game_state.current = GameState.Stopped
        logger.info("cipfried engine stopped.")

    def _wait_for_process(self, poll_interval: float = 0.5) -> None:
        self._process.hook()

        while self._process.pid is None and not self._stop_event.is_set():
            logger.info("Tibia is not running... retrying.")
            time.sleep(poll_interval)
            self._process.hook()

    def _set_stop_handler(self):
        keyboard.add_hotkey(EngineCommand.Stop.value, self._on_stop_hotkey)

    def _on_stop_hotkey(self):
        logger.info("Hotkey %s pressed.", EngineCommand.Stop.value)
        self._shutdown()

    def _shutdown(self):
        if self._ctx.game_state.current == GameState.Stopped:
            return

        self._stop_event.set()
