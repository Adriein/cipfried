from dataclasses import dataclass


@dataclass(frozen=True)
class Item:
    """Represents an item on a tile or in an inventory."""

    id: int
    qty: int = 1


__all__ = ["Item"]
