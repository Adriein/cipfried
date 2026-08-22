from dataclasses import dataclass

from cipfried.core import FrameBuffer, GameState

class State:
    """Mutable wrapper so state changes propagate across all threads referencing Context."""
    def __init__(self, initial: GameState = GameState.Stopped):
        self.current = initial

@dataclass
class Context:
    frame_buffer: FrameBuffer
    game_state: State