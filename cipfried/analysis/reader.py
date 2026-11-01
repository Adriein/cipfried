from cipfried.analysis.errors import TruncatedMessage


class ByteReader:
    """Sequential little-endian reader over a payload.

    Parsers receive a reader positioned immediately after the opcode and must
    advance it by exactly the bytes their message owns. The pipeline then
    continues with whatever remains.
    """

    def __init__(self, data: bytes) -> None:
        self._data = memoryview(data)
        self._position = 0

    @property
    def position(self) -> int:
        return self._position

    @property
    def remaining(self) -> int:
        return len(self._data) - self._position

    @property
    def eof(self) -> bool:
        return self.remaining == 0

    def read_u8(self) -> int:
        return self._read(1)[0]

    def read_u16(self) -> int:
        return int.from_bytes(self._read(2), "little")

    def read_u32(self) -> int:
        return int.from_bytes(self._read(4), "little")

    def read_bytes(self, size: int) -> bytes:
        if size < 0:
            raise ValueError("size must not be negative")

        return self._read(size)

    def skip(self, size: int) -> None:
        if size < 0:
            raise ValueError("size must not be negative")

        self._read(size)

    def peek_u8(self) -> int:
        return self._peek(1)[0]

    def _read(self, size: int) -> bytes:
        if size > self.remaining:
            raise TruncatedMessage(
                f"need {size} bytes at offset {self._position}, only {self.remaining} available"
            )

        start = self._position
        self._position += size
        return bytes(self._data[start : self._position])

    def _peek(self, size: int) -> bytes:
        if size > self.remaining:
            raise TruncatedMessage(
                f"need {size} bytes at offset {self._position}, only {self.remaining} available"
            )

        return bytes(self._data[self._position : self._position + size])


__all__ = ["ByteReader"]
