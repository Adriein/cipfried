from dataclasses import dataclass

from cipfried.core import FrameBuffer, GameState

@dataclass
class Context:
    frame_buffer: FrameBuffer
    game_state: GameState