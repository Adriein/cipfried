import threading
from typing import Generic, TypeVar

T = TypeVar("T")


class LatestValue(Generic[T]):
    """Single-slot, latest-wins handoff between threads.

    Producers overwrite the slot; consumers always read the most recent value.
    Nothing is queued, so a slow consumer cannot build a backlog of stale
    packets. Use ``snapshot`` in a loop, or ``wait_next`` to block until a new
    value arrives.
    """

    def __init__(self, initial: T | None = None) -> None:
        self._condition = threading.Condition()
        self._value = initial
        self._version = 0

    @property
    def version(self) -> int:
        with self._condition:
            return self._version

    def set(self, value: T) -> int:
        with self._condition:
            self._value = value
            self._version += 1
            self._condition.notify_all()
            return self._version

    def get(self) -> T | None:
        with self._condition:
            return self._value

    def snapshot(self) -> tuple[int, T | None]:
        with self._condition:
            return self._version, self._value

    def wait_next(self, after_version: int, timeout: float | None = None) -> tuple[int, T] | None:
        with self._condition:
            if not self._condition.wait_for(lambda: self._version > after_version, timeout):
                return None

            if self._value is None:
                return None

            return self._version, self._value

    def clear(self) -> None:
        with self._condition:
            self._value = None
            self._version += 1
            self._condition.notify_all()


__all__ = ["LatestValue"]
