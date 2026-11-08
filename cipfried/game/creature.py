from dataclasses import dataclass, field

from cipfried.game.position import Position


@dataclass
class Creature:
    """Represents a creature (player, monster, NPC) in the game world."""

    id: int
    name: str = ""
    creature_type: int = 0
    health_percentage: int = 100
    facing_dir: int = 0
    speed: int = 0
    position: Position = field(default_factory=lambda: Position(0, 0, 0))


__all__ = ["Creature"]
