from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Position:
    x: int
    y: int
    z: int


__all__ = ["Position"]
