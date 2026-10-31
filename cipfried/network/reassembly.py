import logging
from typing import Final

logger = logging.getLogger(__name__)

SEQUENCE_MASK: Final = 0xFFFFFFFF
SEQUENCE_MODULUS: Final = 0x100000000
SEQUENCE_HALF: Final = 0x80000000


def _sequence_add(sequence: int, length: int) -> int:
    return (sequence + length) & SEQUENCE_MASK


def _sequence_difference(left: int, right: int) -> int:
    """Returns the signed distance from right to left, accounting for wraparound."""
    return ((left - right + SEQUENCE_HALF) & SEQUENCE_MASK) - SEQUENCE_HALF


def _sequence_less(left: int, right: int) -> bool:
    return _sequence_difference(left, right) < 0


def _sequence_greater(left: int, right: int) -> bool:
    return _sequence_difference(left, right) > 0


def _sequence_less_equal(left: int, right: int) -> bool:
    return _sequence_difference(left, right) <= 0


class TcpReassembler:
    MAX_PENDING_BYTES: Final = 1024 * 1024

    def __init__(self) -> None:
        self._next_sequence: int | None = None
        self._pending: dict[int, bytes] = {}
        self._pending_bytes = 0

    def feed(self, sequence: int, payload: bytes) -> bytes:
        if not payload:
            return b""

        sequence &= SEQUENCE_MASK

        if self._next_sequence is None:
            self._next_sequence = sequence

        if _sequence_less(sequence, self._next_sequence):
            overlap = _sequence_difference(self._next_sequence, sequence)

            if overlap >= len(payload):
                return b""

            payload = payload[overlap:]
            sequence = _sequence_add(sequence, overlap)

        if _sequence_greater(sequence, self._next_sequence):
            self._store(sequence, payload)

            if self._pending_bytes > self.MAX_PENDING_BYTES:
                output = bytearray()
                self._recover_pending(output)

                return bytes(output)

            return b""

        output = bytearray(payload)
        self._next_sequence = _sequence_add(self._next_sequence, len(payload))
        self._drain(output)

        return bytes(output)

    def reset(self) -> None:
        self._next_sequence = None
        self._pending.clear()
        self._pending_bytes = 0

    def _store(self, sequence: int, payload: bytes) -> None:
        previous = self._pending.get(sequence)

        if previous is not None:
            self._pending_bytes -= len(previous)

        self._pending[sequence] = payload
        self._pending_bytes += len(payload)

    def _recover_pending(self, output: bytearray) -> None:
        if not self._pending:
            return

        oldest = next(iter(self._pending))

        for sequence in self._pending:
            if _sequence_less(sequence, oldest):
                oldest = sequence

        logger.warning(
            "TCP reassembly buffer exceeded %d bytes; skipping ahead to pending sequence %d.",
            self.MAX_PENDING_BYTES,
            oldest,
        )
        self._next_sequence = oldest
        self._drain(output)

    def _drain(self, output: bytearray) -> None:
        if self._next_sequence is None:
            return

        while True:
            stale = [
                sequence
                for sequence, payload in self._pending.items()
                if _sequence_less_equal(_sequence_add(sequence, len(payload)), self._next_sequence)
            ]

            for sequence in stale:
                self._pending_bytes -= len(self._pending.pop(sequence))

            covering = next(
                (
                    (sequence, payload)
                    for sequence, payload in self._pending.items()
                    if _sequence_less_equal(sequence, self._next_sequence)
                    and _sequence_less(self._next_sequence, _sequence_add(sequence, len(payload)))
                ),
                None,
            )

            if covering is None:
                return

            sequence, payload = covering
            offset = _sequence_difference(self._next_sequence, sequence)
            output.extend(payload[offset:])
            self._next_sequence = _sequence_add(self._next_sequence, len(payload) - offset)
            self._pending_bytes -= len(self._pending.pop(sequence))
