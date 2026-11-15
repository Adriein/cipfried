from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from cipfried.bot.fsm import State, StateMachine
from cipfried.game.position import Position

if TYPE_CHECKING:
    from cipfried.core.context import Context
    from cipfried.game.world import WorldState

logger = logging.getLogger(__name__)


class Pathfinder:
    """Calculates route of positions using WorldState tiles and obstacles.

    (Algorithm intentionally left empty as requested).
    """

    def find_path(self, world: WorldState, start: Position, goal: Position) -> list[Position]:
        logger.info(f"[Pathfinder] Calculating path from {start} to {goal} using WorldState tiles...")
        # No algorithm implemented; returns placeholder path
        return [goal]


class IdleState(State):
    """Player is standing still, ready for commands or targets."""

    def on_enter(self, fsm: StateMachine, ctx: Context) -> None:
        logger.info("[IdleState] Entered Idle state.")

    def update(self, fsm: StateMachine, ctx: Context, now: float) -> None:
        logger.info(f"[IdleState] Tick at {now:.2f}. Standing at {ctx.world.player_position}.")

    def on_exit(self, fsm: StateMachine, ctx: Context) -> None:
        logger.info("[IdleState] Exiting Idle state.")


class WalkingState(State):
    """State executing movement along a path to a target destination."""

    def __init__(self, destination: Position, pathfinder: Pathfinder | None = None) -> None:
        self.destination = destination
        self.pathfinder = pathfinder if pathfinder is not None else Pathfinder()
        self.path: list[Position] = []

    def on_enter(self, fsm: StateMachine, ctx: Context) -> None:
        player_pos = ctx.world.player_position
        logger.info(f"[WalkingState] Started walking towards {self.destination}.")

        if player_pos is not None:
            # Planner generates the path using WorldState
            self.path = self.pathfinder.find_path(ctx.world, player_pos, self.destination)

    def update(self, fsm: StateMachine, ctx: Context, now: float) -> None:
        logger.info(f"[WalkingState] Tick at {now:.2f}. Steps remaining: {len(self.path)}.")

        # Logic outline (no algorithm):
        # 1. Check if at destination -> fsm.change_state(IdleState(), ctx)
        # 2. Check if animation/step delay is still active -> wait
        # 3. Take next step from self.path

    def on_exit(self, fsm: StateMachine, ctx: Context) -> None:
        logger.info(f"[WalkingState] Stopped walking towards {self.destination}.")


__all__ = ["IdleState", "Pathfinder", "WalkingState"]
