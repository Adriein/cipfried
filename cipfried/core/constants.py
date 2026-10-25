from enum import Enum
from typing import Final

TIBIA_SERVER_PORT: Final = 7171


class GameState(Enum):
    Running = 1
    Paused = 2
    Stopped = 3


class EngineCommand(Enum):
    Stop = "p"
