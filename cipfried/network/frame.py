from dataclasses import dataclass
from typing import Final

from cipfried.network.xtea import XTEA_BLOCK_SIZE

PACKET_HEADER_SIZE: Final = 6
PACKET_COMPRESSED_FLAG: Final = 0xC000
VALID_COMPRESSION_FLAGS: Final = frozenset((0, PACKET_COMPRESSED_FLAG))
MAX_FRAME_SIZE: Final = 0x10000
MAX_BLOCK_COUNT: Final = (MAX_FRAME_SIZE - PACKET_HEADER_SIZE) // XTEA_BLOCK_SIZE


@dataclass(frozen=True)
class FrameHeader:
    block_count: int
    sequence: int
    compressed: bool

    @property
    def size(self) -> int:
        return PACKET_HEADER_SIZE + self.block_count * XTEA_BLOCK_SIZE


def parse_header(buffer: bytes | bytearray, offset: int = 0) -> FrameHeader | None:
    """Parses a frame header, returning None when it is incomplete or invalid."""
    if len(buffer) - offset < PACKET_HEADER_SIZE:
        return None

    block_count = int.from_bytes(buffer[offset : offset + 2], "little")
    sequence = int.from_bytes(buffer[offset + 2 : offset + 4], "little")
    compression_flag = int.from_bytes(buffer[offset + 4 : offset + 6], "little")

    if block_count == 0 or block_count > MAX_BLOCK_COUNT or compression_flag not in VALID_COMPRESSION_FLAGS:
        return None

    return FrameHeader(
        block_count=block_count,
        sequence=sequence,
        compressed=compression_flag == PACKET_COMPRESSED_FLAG,
    )
