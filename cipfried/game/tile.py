from dataclasses import dataclass, field
from typing import Final

from cipfried.game.creature import Creature
from cipfried.game.item import Item
from cipfried.game.position import Position

# Tibia viewport dimensions (in tiles)
MAP_WIDTH: Final[int] = 18   # Number of columns (X axis)
MAP_HEIGHT: Final[int] = 14  # Squares down one column (Y axis)

# Player's offset from the upper-left corner of the viewport
PLAYER_OFFSET_X: Final[int] = 8  # 8 tiles left of the player (range: player.x - 8 .. player.x + 9)
PLAYER_OFFSET_Y: Final[int] = 6  # 6 tiles above the player (range: player.y - 6 .. player.y + 7)


def tile_position_from_index(
    player_pos: Position,
    square_index: int,
    *,
    z: int | None = None,
    columns: int = MAP_WIDTH,
    rows: int = MAP_HEIGHT,
) -> Position:
    """Calculates the world Position of a square given its sequential index.

    Squares are traversed column by column (downwards first, then to the right):
      - col = square_index // rows
      - row = square_index % rows
    The player is located in the middle of the screen at (PLAYER_OFFSET_X, PLAYER_OFFSET_Y).
    """
    col = (square_index % (columns * rows)) // rows
    row = (square_index % (columns * rows)) % rows
    floor = player_pos.z if z is None else z

    return Position(
        x=player_pos.x - PLAYER_OFFSET_X + col,
        y=player_pos.y - PLAYER_OFFSET_Y + row,
        z=floor,
    )


@dataclass
class Tile:
    """Represents a map square with its ground, stacked items, and creatures."""

    position: Position
    ground_id: int | None = None
    items: list[Item] = field(default_factory=list)
    creatures: list[Creature] = field(default_factory=list)

    def add_item(self, item: Item) -> None:
        self.items.append(item)

    def add_creature(self, creature: Creature) -> None:
        creature.position = self.position
        self.creatures.append(creature)


__all__ = [
    "MAP_HEIGHT",
    "MAP_WIDTH",
    "PLAYER_OFFSET_X",
    "PLAYER_OFFSET_Y",
    "Tile",
    "tile_position_from_index",
]
