from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable

from cipfried.config.settings import DEFAULT_BOT_TICK_INTERVAL
from cipfried.core.context import Context

logger = logging.getLogger(__name__)

TickHandler = Callable[[Context, float], None]


class BotWorker:
    """Tick-based decision worker running on a dedicated thread.

    Decoupled from network packet parsing. Evaluates world state periodically
    (e.g. 50ms ticks) to execute state machine transitions and bot actions.
    """

    def __init__(
        self,
        context: Context,
        interval: float = DEFAULT_BOT_TICK_INTERVAL,
        *,
        on_tick: TickHandler | None = None,
    ) -> None:
        self._ctx = context
        self._interval = interval
        self._on_tick = on_tick
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._tick_count: int = 0
        self._last_tick_time: float = 0.0

    @property
    def context(self) -> Context:
        return self._ctx

    @property
    def interval(self) -> float:
        return self._interval

    @interval.setter
    def interval(self, value: float) -> None:
        self._interval = value

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def tick_count(self) -> int:
        return self._tick_count

    @property
    def last_tick_time(self) -> float:
        return self._last_tick_time

    def set_tick_handler(self, handler: TickHandler | None) -> None:
        self._on_tick = handler

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="cipfried-game",
            daemon=True,
        )
        self._thread.start()
        logger.info("Bot worker started (interval: %.3fs).", self._interval)

    def stop(self, timeout: float = 2.0) -> None:
        self._stop_event.set()
        thread = self._thread
        self._thread = None

        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=timeout)
            logger.info("Bot worker stopped.")

    def step(self, now: float | None = None) -> None:
        """Execute a single tick synchronously.

        Useful for deterministic testing and manual stepping without background threads.
        """
        current_time = time.monotonic() if now is None else now
        self._last_tick_time = current_time
        self._tick_count += 1

        self.on_tick(self._ctx, current_time)

    def on_tick(self, context: Context, now: float) -> None:
        """Called every tick. Override in subclasses or provide an on_tick handler."""
        if self._on_tick is not None:
            try:
                self._on_tick(context, now)
            except Exception:
                logger.exception("Error in bot tick handler.")

    def _run(self) -> None:
        logger.debug("Bot loop entered.")
        while not self._stop_event.is_set():
            start = time.monotonic()
            try:
                self.step(start)
            except Exception:
                logger.exception("Unexpected error during bot tick.")

            elapsed = time.monotonic() - start
            sleep_time = max(0.0, self._interval - elapsed)
            if self._stop_event.wait(sleep_time):
                break
        logger.debug("Bot loop exited.")


__all__ = ["BotWorker", "TickHandler"]
