import logging
from dataclasses import dataclass

from cipfried.os import Process


logger = logging.getLogger(__name__)

XTEA_KEY_SIZE = 16
XTEA_KEY_ANCHOR = bytes.fromhex("ffffffffffffff3f0400000000000000")
XTEA_KEY_ANCHOR_DISTANCE = 160
XTEA_KEY_OFFSET = 8 + XTEA_KEY_SIZE


@dataclass(frozen=True)
class XteaKey:
    segments: tuple[int, int, int, int]

    @classmethod
    def from_bytes(cls, raw: bytes) -> "XteaKey":
        if len(raw) != XTEA_KEY_SIZE:
            raise ValueError(f"XTEA key must be {XTEA_KEY_SIZE} bytes long")

        return cls((
            int.from_bytes(raw[0:4], "little"),
            int.from_bytes(raw[4:8], "little"),
            int.from_bytes(raw[8:12], "little"),
            int.from_bytes(raw[12:16], "little"),
        ))

    def to_bytes(self) -> bytes:
        return b"".join(segment.to_bytes(4, "little") for segment in self.segments)


def find_xtea_key(process: Process) -> XteaKey:
    """Finds the XTEA key in the Tibia process memory using its anchor."""
    addresses = process.scan_memory(XTEA_KEY_ANCHOR)
    key_address = None

    for previous, current in zip(addresses, addresses[1:]):
        if current - previous == XTEA_KEY_ANCHOR_DISTANCE:
            key_address = current - XTEA_KEY_OFFSET

    if key_address is None:
        raise ValueError("No XTEA key found in process memory")

    key = XteaKey.from_bytes(process.read_memory(key_address, XTEA_KEY_SIZE))
    logger.info("XTEA key found.")

    return key
