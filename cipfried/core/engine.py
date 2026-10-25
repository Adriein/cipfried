import logging
import threading
import time
from collections.abc import Callable

import keyboard

from cipfried.core.constants import EngineCommand, GameState
from cipfried.core.context import Context, State
from cipfried.os.memory import Memory
from cipfried.os.process import Process

logger = logging.getLogger(__name__)


class Engine:
    def __init__(self, process: Process | None = None) -> None:
        self._process = process if process is not None else Process(Memory())
        self._state = State()
        self._ctx = Context(game_state=self._state)
        self._stop_event = threading.Event()
        self._hotkey_handle: Callable[[], None] | None = None

    def start(self) -> None:
        if self._ctx.game_state.current != GameState.Stopped:
            logger.warning("Engine is already running or starting.")
            return

        self._stop_event.clear()
        self._ctx.game_state.current = GameState.Starting
        logger.info("Starting cipfried engine...")

        try:
            self._set_stop_handler()
            self._wait_for_process()

            if self._stop_event.is_set():
                return

            self._ctx.game_state.current = GameState.Running
            logger.info("cipfried engine running (PID: %s).", self._process.pid)
            self._monitor_process()
        finally:
            self._ctx.game_state.current = GameState.Stopped
            self._remove_stop_handler()
            logger.info("cipfried engine stopped.")

    def stop(self) -> None:
        if self._ctx.game_state.current == GameState.Stopped:
            return

        self._ctx.game_state.current = GameState.Stopping
        self._stop_event.set()

    def _wait_for_process(self, poll_interval: float = 0.5) -> None:
        self._process.hook()

        if self._process.pid is not None:
            logger.info("Hooked to %s process (PID: %s).", self._process.name, self._process.pid)
            return

        logger.info("%s is not running; waiting...", self._process.name)

        while not self._stop_event.is_set():
            time.sleep(poll_interval)
            self._process.hook()

            if self._process.pid is not None:
                logger.info("Hooked to %s process (PID: %s).", self._process.name, self._process.pid)
                return

    def _monitor_process(self, poll_interval: float = 1.0) -> None:
        while not self._stop_event.wait(poll_interval):
            if self._process.is_alive():
                continue

            logger.warning("%s process exited; waiting for restart...", self._process.name)
            self._ctx.game_state.current = GameState.Starting
            self._wait_for_process()

            if self._stop_event.is_set():
                return

            self._ctx.game_state.current = GameState.Running
            logger.info("cipfried engine running (PID: %s).", self._process.pid)

    def _set_stop_handler(self) -> None:
        if self._hotkey_handle is not None:
            return

        self._hotkey_handle = keyboard.add_hotkey(EngineCommand.Stop.value, self._on_stop_hotkey)

    def _remove_stop_handler(self) -> None:
        if self._hotkey_handle is None:
            return

        keyboard.remove_hotkey(self._hotkey_handle)
        self._hotkey_handle = None

    def _on_stop_hotkey(self) -> None:
        logger.info("Hotkey %s pressed.", EngineCommand.Stop.value)
        self.stop()
