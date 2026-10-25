from enum import Enum


class GameState(Enum):
    Stopped = 1
    Starting = 2
    Running = 3
    Stopping = 4


class EngineCommand(Enum):
    Stop = "p"
