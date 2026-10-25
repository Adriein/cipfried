from enum import Enum
from typing import Final

TIBIA_SERVER_PORT: Final = 7171


class GameState(Enum):
    Stopped = 1
    Starting = 2
    Running = 3
    Stopping = 4


class EngineCommand(Enum):
    Stop = "p"
