from dataclasses import dataclass, field

from cipfried.core.constants import GameState
from cipfried.game.world import WorldState


class State:
    """Mutable wrapper so state changes propagate across all threads referencing Context."""

    def __init__(self, initial: GameState = GameState.Stopped) -> None:
        self.current: GameState = initial


@dataclass
class Context:
    game_state: State
    world: WorldState = field(default_factory=WorldState)


__all__ = ["Context", "State"]
