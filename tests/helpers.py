from __future__ import annotations

import zlib

from scapy.layers.inet import IP, TCP
from scapy.packet import Raw

from cipfried.network.frame import PACKET_COMPRESSED_FLAG
from cipfried.network.xtea import XTEA_BLOCK_SIZE, XteaCipher, XteaKey

KEY = XteaKey((0x01234567, 0x89ABCDEF, 0xFEDCBA98, 0x76543210))
OTHER_KEY = XteaKey((0x11111111, 0x22222222, 0x33333333, 0x44444444))
CLIENT_IP = "192.0.2.10"
SERVER_IP = "203.0.113.10"
OTHER_SERVER_IP = "203.0.113.20"
SERVER_PORT = 7171
CLIENT_PORT = 50_000
SYNC_FLUSH = b"\x00\x00\xff\xff"


def make_cipher(key: XteaKey = KEY) -> XteaCipher:
    return XteaCipher(key)


def pad_payload(payload: bytes) -> bytes:
    padding = (-len(payload) - 1) % XTEA_BLOCK_SIZE
    return bytes([padding]) + payload + b"\x00" * padding


def make_frame_from_encoded(
    cipher: XteaCipher,
    sequence: int,
    encoded: bytes,
    *,
    compressed: bool = False,
) -> bytes:
    plaintext = pad_payload(encoded)
    block_count = len(plaintext) // XTEA_BLOCK_SIZE
    compression_flag = PACKET_COMPRESSED_FLAG if compressed else 0
    header = (
        block_count.to_bytes(2, "little")
        + sequence.to_bytes(2, "little")
        + compression_flag.to_bytes(2, "little")
    )
    return header + cipher.encrypt(plaintext)


def compress_payload(payload: bytes, encoder: zlib.Compress | None = None) -> bytes:
    compressor = encoder if encoder is not None else zlib.compressobj(wbits=-15)
    data = compressor.compress(payload) + compressor.flush(zlib.Z_SYNC_FLUSH)

    if data.endswith(SYNC_FLUSH):
        data = data[: -len(SYNC_FLUSH)]

    return data


def make_frame(
    cipher: XteaCipher,
    sequence: int,
    payload: bytes,
    *,
    compressed: bool = False,
    encoder: zlib.Compress | None = None,
) -> bytes:
    encoded = compress_payload(payload, encoder) if compressed else payload
    return make_frame_from_encoded(cipher, sequence, encoded, compressed=compressed)


def make_tcp_packet(
    payload: bytes,
    *,
    from_client: bool = False,
    sequence: int = 1,
    source_ip: str = CLIENT_IP,
    destination_ip: str = SERVER_IP,
    source_port: int = CLIENT_PORT,
    destination_port: int = SERVER_PORT,
    flags: str = "PA",
) -> IP:
    packet = IP(src=source_ip, dst=destination_ip) / TCP(
        sport=source_port,
        dport=destination_port,
        seq=sequence,
        flags=flags,
    )

    if payload:
        packet = packet / Raw(load=payload)

    return packet
