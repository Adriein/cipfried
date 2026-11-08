import threading
from dataclasses import dataclass, field

from cipfried.game.messages import CreatureMovement, FullMap, GameMessage, LoginSuccess
from cipfried.game.position import Position


@dataclass
class Creature:
    id: int
    name: str = ""
    position: Position = field(default_factory=lambda: Position(0, 0, 0))


class WorldState:
    """Thread-safe store of the current in-game world state.

    Updated by message listeners and queried by bot decision loops.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._player_id: int | None = None
        self._player_position: Position | None = None

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

    def apply_message(self, message: GameMessage) -> None:
        """Update world state from a decoded game message."""
        with self._lock:
            if isinstance(message, LoginSuccess):
                self._player_id = message.player_id
            elif isinstance(message, CreatureMovement):
                if self._player_position is not None and message.old_position == self._player_position:
                    self._player_position = message.new_position
            elif isinstance(message, FullMap):
                self._player_position = message.player_position

    def reset(self) -> None:
        with self._lock:
            self._player_id = None
            self._player_position = None


__all__ = ["Creature", "WorldState"]
