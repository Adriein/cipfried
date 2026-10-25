import logging
from typing import Final

logger = logging.getLogger(__name__)


class TcpReassembler:
    MAX_PENDING_BYTES: Final = 1024 * 1024

    def __init__(self) -> None:
        self._next_sequence: int | None = None
        self._pending: dict[int, bytes] = {}
        self._pending_bytes = 0

    def feed(self, sequence: int, payload: bytes) -> bytes:
        if not payload:
            return b""

        if self._next_sequence is None:
            self._next_sequence = sequence

        if sequence < self._next_sequence:
            overlap = self._next_sequence - sequence

            if overlap >= len(payload):
                return b""

            sequence += overlap
            payload = payload[overlap:]

        if sequence > self._next_sequence:
            self._store(sequence, payload)

            return b""

        output = bytearray(payload)
        self._next_sequence += len(payload)
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

        if self._pending_bytes > self.MAX_PENDING_BYTES:
            logger.warning("TCP reassembly buffer exceeded %d bytes; dropping pending data.", self.MAX_PENDING_BYTES)
            self._pending.clear()
            self._pending_bytes = 0

    def _drain(self, output: bytearray) -> None:
        if self._next_sequence is None:
            return

        while True:
            stale = [
                sequence
                for sequence, payload in self._pending.items()
                if sequence + len(payload) <= self._next_sequence
            ]

            for sequence in stale:
                self._pending_bytes -= len(self._pending.pop(sequence))

            covering = next(
                (
                    (sequence, payload)
                    for sequence, payload in self._pending.items()
                    if sequence <= self._next_sequence < sequence + len(payload)
                ),
                None,
            )

            if covering is None:
                return

            sequence, payload = covering
            offset = self._next_sequence - sequence
            output.extend(payload[offset:])
            self._next_sequence += len(payload) - offset
            self._pending_bytes -= len(self._pending.pop(sequence))
