from enum import Enum

TIBIA_SERVER_PORT = 7171

class EngineState(Enum):
    Running = 1
    Paused = 2
    Stopped = 3

class EngineCommand(Enum):
    Stop = 'p'