from __future__ import annotations

import logging
import threading

from cipfried.game.creature import Creature
from cipfried.game.messages import CreatureMovement, FullMap, GameMessage, LoginSuccess
from cipfried.game.position import Position
from cipfried.game.tile import Tile

logger = logging.getLogger(__name__)


class WorldState:
    """Thread-safe store of the current in-game world state.

    Updated by message listeners and queried by bot decision loops.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._player_id: int | None = None
        self._player_position: Position | None = None
        self._tiles: dict[Position, Tile] = {}
        self._creatures: dict[int, Creature] = {}

    @property
    def player_id(self) -> int | None:
        with self._lock:
            return self._player_id

    @player_id.setter
    def player_id(self, value: int | None) -> None:
        with self._lock:
            self._player_id = value

    @property
    def player_position(self) -> Position | None:
        with self._lock:
            return self._player_position

    @player_position.setter
    def player_position(self, value: Position | None) -> None:
        with self._lock:
            self._player_position = value

    @property
    def tiles(self) -> dict[Position, Tile]:
        """Thread-safe snapshot copy of the world tiles."""
        with self._lock:
            return dict(self._tiles)

    @property
    def creatures(self) -> dict[int, Creature]:
        """Thread-safe snapshot copy of known creatures."""
        with self._lock:
            return dict(self._creatures)

    def get_tile(self, position: Position) -> Tile | None:
        with self._lock:
            return self._tiles.get(position)

    def set_tile(self, tile: Tile) -> None:
        with self._lock:
            self._tiles[tile.position] = tile
            for creature in tile.creatures:
                self._creatures[creature.id] = creature

    def get_creature(self, creature_id: int) -> Creature | None:
        with self._lock:
            return self._creatures.get(creature_id)

    def apply_message(self, message: GameMessage) -> None:
        """Update world state from a decoded game message."""
        with self._lock:
            if isinstance(message, LoginSuccess):
                self._player_id = message.player_id
            elif isinstance(message, FullMap):
                self._player_position = message.player_position

                for tile in message.tiles:
                    self._tiles[tile.position] = tile

                    for creature in tile.creatures:
                        self._creatures[creature.id] = creature
            elif isinstance(message, CreatureMovement):
                self._handle_creature_movement(message)

    def _handle_creature_movement(self, message: CreatureMovement) -> None:
        is_player = self._player_position is not None and message.old_position == self._player_position

        if is_player:
            self._player_position = message.new_position

        old_tile = self._tiles.get(message.old_position)
        new_tile = self._tiles.get(message.new_position)

        if old_tile and new_tile and old_tile.creatures:
            # For now we are assuming that we have 1 creature per tile
            for creature in old_tile.creatures:
                old_tile.remove_creature(creature)

                creature.position = message.new_position

                self._creatures[creature.id] = creature

                new_tile.add_creature(creature)

    def reset(self) -> None:
        with self._lock:
            self._player_id = None
            self._player_position = None
            self._tiles.clear()
            self._creatures.clear()


__all__ = ["Creature", "WorldState"]
