import random
import struct

import pytest

from cipfried.network.xtea import (
    UINT32_MASK,
    XTEA_DELTA,
    XTEA_ROUNDS,
    XteaCipher,
    XteaKey,
)


def reference_encrypt_block(key: tuple[int, int, int, int], block: bytes) -> bytes:
    v0, v1 = struct.unpack("<2I", block)
    total = 0

    for _ in range(XTEA_ROUNDS):
        v0 = (v0 + ((((v1 << 4) ^ (v1 >> 5)) + v1) ^ (total + key[total & 3]))) & UINT32_MASK
        total = (total + XTEA_DELTA) & UINT32_MASK
        v1 = (v1 + ((((v0 << 4) ^ (v0 >> 5)) + v0) ^ (total + key[(total >> 11) & 3]))) & UINT32_MASK

    return struct.pack("<2I", v0, v1)


def reference_decrypt_block(key: tuple[int, int, int, int], block: bytes) -> bytes:
    v0, v1 = struct.unpack("<2I", block)
    total = (XTEA_DELTA * XTEA_ROUNDS) & UINT32_MASK

    for _ in range(XTEA_ROUNDS):
        v1 = (v1 - ((((v0 << 4) ^ (v0 >> 5)) + v0) ^ (total + key[(total >> 11) & 3]))) & UINT32_MASK
        total = (total - XTEA_DELTA) & UINT32_MASK
        v0 = (v0 - ((((v1 << 4) ^ (v1 >> 5)) + v1) ^ (total + key[total & 3]))) & UINT32_MASK

    return struct.pack("<2I", v0, v1)


def test_encrypt_matches_reference() -> None:
    random_source = random.Random(1234)

    for _ in range(250):
        key = XteaKey(tuple(random_source.getrandbits(32) for _ in range(4)))
        block = bytes(random_source.getrandbits(8) for _ in range(8))

        assert XteaCipher(key).encrypt(block) == reference_encrypt_block(key.segments, block)


def test_decrypt_matches_reference() -> None:
    random_source = random.Random(5678)

    for _ in range(250):
        key = XteaKey(tuple(random_source.getrandbits(32) for _ in range(4)))
        block = bytes(random_source.getrandbits(8) for _ in range(8))

        assert XteaCipher(key).decrypt(block) == reference_decrypt_block(key.segments, block)


def test_key_roundtrip() -> None:
    key = XteaKey.from_bytes(bytes(range(16)))

    assert key.to_bytes() == bytes(range(16))


def test_key_rejects_invalid_length() -> None:
    with pytest.raises(ValueError):
        XteaKey.from_bytes(b"short")


def test_cipher_rejects_partial_blocks() -> None:
    with pytest.raises(ValueError):
        XteaCipher(XteaKey((0, 0, 0, 0))).encrypt(b"not aligned")
