from dataclasses import dataclass

from cipfried.game.position import Position


@dataclass(frozen=True)
class GameMessage:
    """Base type for a decoded server message.

    Message classes should subclass this and add the fields their parser
    extracts. Keeping the opcode on every message lets downstream code route
    without knowing the parser that produced it.
    """

    opcode: int


@dataclass(frozen=True)
class CreatureMovement(GameMessage):
    old_position: Position
    old_stackpos: int
    new_position: Position


__all__ = ["CreatureMovement", "GameMessage"]
