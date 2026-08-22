from enum import Enum
from dataclasses import dataclass

from cipfried.core.frame_buffer import FrameBuffer

TIBIA_SERVER_PORT = 7171

class GameState(Enum):
    Running = 1
    Paused = 2
    Stopped = 3

class EngineCommand(Enum):
    Stop = 'p'

class State:
    """Mutable wrapper so state changes propagate across all threads referencing Context."""
    def __init__(self, initial: GameState = GameState.Stopped):
        self.current = initial

@dataclass
class Context:
    frame_buffer: FrameBuffer
    game_state: State