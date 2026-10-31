from __future__ import annotations

import logging
import struct
from dataclasses import dataclass
from typing import Protocol

logger = logging.getLogger(__name__)

XTEA_BLOCK_SIZE = 8
XTEA_KEY_SIZE = 16
XTEA_ROUNDS = 32
XTEA_DELTA = 0x9E3779B9
XTEA_KEY_ANCHOR = bytes.fromhex("ffffffffffffff3f0400000000000000")
XTEA_KEY_ANCHOR_DISTANCE = 160
XTEA_KEY_OFFSET = 8 + XTEA_KEY_SIZE
UINT32_MASK = 0xFFFFFFFF


class MemoryProcess(Protocol):
    def scan_memory(self, pattern: bytes) -> list[int]: ...

    def read_memory(self, address: int, size: int) -> bytes: ...


@dataclass(frozen=True)
class XteaKey:
    segments: tuple[int, int, int, int]

    @classmethod
    def from_bytes(cls, raw: bytes) -> XteaKey:
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


class XteaCipher:
    def __init__(self, key: XteaKey) -> None:
        if len(key.segments) != 4:
            raise ValueError("XTEA key must contain exactly four 32-bit segments")

        if any(segment < 0 or segment > UINT32_MASK for segment in key.segments):
            raise ValueError("XTEA key segments must be unsigned 32-bit integers")

        self._key = key.segments

    def decrypt(self, data: bytes) -> bytes:
        self._validate_block_data(data)

        return b"".join(
            self._decrypt_block(data[offset : offset + XTEA_BLOCK_SIZE])
            for offset in range(0, len(data), XTEA_BLOCK_SIZE)
        )

    def encrypt(self, data: bytes) -> bytes:
        self._validate_block_data(data)

        return b"".join(
            self._encrypt_block(data[offset : offset + XTEA_BLOCK_SIZE])
            for offset in range(0, len(data), XTEA_BLOCK_SIZE)
        )

    def _decrypt_block(self, block: bytes) -> bytes:
        v0, v1 = struct.unpack("<2I", block)
        total = (XTEA_DELTA * XTEA_ROUNDS) & UINT32_MASK

        for _ in range(XTEA_ROUNDS):
            v1 = (v1 - ((((v0 << 4) ^ (v0 >> 5)) + v0) ^ (total + self._key[(total >> 11) & 3]))) & UINT32_MASK
            total = (total - XTEA_DELTA) & UINT32_MASK
            v0 = (v0 - ((((v1 << 4) ^ (v1 >> 5)) + v1) ^ (total + self._key[total & 3]))) & UINT32_MASK

        return struct.pack("<2I", v0, v1)

    def _encrypt_block(self, block: bytes) -> bytes:
        v0, v1 = struct.unpack("<2I", block)
        total = 0

        for _ in range(XTEA_ROUNDS):
            v0 = (v0 + ((((v1 << 4) ^ (v1 >> 5)) + v1) ^ (total + self._key[total & 3]))) & UINT32_MASK
            total = (total + XTEA_DELTA) & UINT32_MASK
            v1 = (v1 + ((((v0 << 4) ^ (v0 >> 5)) + v0) ^ (total + self._key[(total >> 11) & 3]))) & UINT32_MASK

        return struct.pack("<2I", v0, v1)

    @staticmethod
    def _validate_block_data(data: bytes) -> None:
        if len(data) % XTEA_BLOCK_SIZE != 0:
            raise ValueError(f"XTEA data length must be a multiple of {XTEA_BLOCK_SIZE} bytes")


def find_xtea_key_addresses(process: MemoryProcess) -> list[int]:
    """Returns every candidate XTEA key address found via the anchor pair."""
    addresses = process.scan_memory(XTEA_KEY_ANCHOR)
    key_addresses: list[int] = []

    for previous, current in zip(addresses, addresses[1:], strict=False):
        if current - previous == XTEA_KEY_ANCHOR_DISTANCE:
            key_address = current - XTEA_KEY_OFFSET

            if key_address not in key_addresses:
                key_addresses.append(key_address)

    if not key_addresses:
        raise ValueError("No XTEA key found in process memory")

    return key_addresses


def find_xtea_key(process: MemoryProcess) -> XteaKey:
    """Finds the last XTEA key candidate in the Tibia process memory."""
    key = XteaKey.from_bytes(process.read_memory(find_xtea_key_addresses(process)[-1], XTEA_KEY_SIZE))
    logger.debug("XTEA key found.")

    return key
