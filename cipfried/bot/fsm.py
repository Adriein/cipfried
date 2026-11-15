from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cipfried.core.context import Context

logger = logging.getLogger(__name__)


class State:
    """Base interface for all bot states."""

    def on_enter(self, fsm: StateMachine, ctx: Context) -> None:
        """Called once when entering this state."""

    def update(self, fsm: StateMachine, ctx: Context, now: float) -> None:
        """Called every bot tick while this state is active."""

    def on_exit(self, fsm: StateMachine, ctx: Context) -> None:
        """Called once when exiting this state."""


class StateMachine:
    """Manages state transitions and dispatches bot ticks."""

    def __init__(self, initial_state: State) -> None:
        self._current_state: State = initial_state
        self._started: bool = False

    @property
    def current_state(self) -> State:
        return self._current_state

    def change_state(self, new_state: State, ctx: Context) -> None:
        old_name = type(self._current_state).__name__
        new_name = type(new_state).__name__
        logger.info("FSM transition: %s -> %s", old_name, new_name)

        self._current_state.on_exit(self, ctx)
        self._current_state = new_state
        self._current_state.on_enter(self, ctx)

    def tick(self, ctx: Context, now: float) -> None:
        """Dispatch function passed directly to BotWorker as on_tick."""
        if not self._started:
            self._started = True
            self._current_state.on_enter(self, ctx)

        self._current_state.update(self, ctx, now)


__all__ = ["State", "StateMachine"]
