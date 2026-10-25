from dataclasses import dataclass

from cipfried.core.constants import GameState


class State:
    """Mutable wrapper so state changes propagate across all threads referencing Context."""

    def __init__(self, initial: GameState = GameState.Stopped) -> None:
        self.current: GameState = initial


@dataclass
class Context:
    game_state: State


__all__ = ["Context", "State"]
