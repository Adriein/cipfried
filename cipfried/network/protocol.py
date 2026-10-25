import logging
from dataclasses import dataclass

from cipfried.network.decompressor import TibiaDecompressionError, TibiaDecompressor
from cipfried.network.xtea import XTEA_BLOCK_SIZE, XteaCipher

logger = logging.getLogger(__name__)

PACKET_HEADER_SIZE = 6
PACKET_COMPRESSED_FLAG = 0xC000
VALID_COMPRESSION_FLAGS = frozenset((0, PACKET_COMPRESSED_FLAG))


class TibiaProtocolError(ValueError):
    pass


@dataclass(frozen=True)
class TibiaPacket:
    from_client: bool
    sequence: int
    compressed: bool
    decrypted: bool
    payload: bytes
    encrypted_payload: bytes

    @property
    def command(self) -> int | None:
        return self.payload[0] if self.payload else None


class TibiaStreamDecoder:
    def __init__(self, cipher: XteaCipher | None, from_client: bool) -> None:
        self._cipher = cipher
        self._from_client = from_client
        self._buffer = bytearray()
        self._decompressor = TibiaDecompressor()

    def set_cipher(self, cipher: XteaCipher | None) -> None:
        self._cipher = cipher

    def reset(self) -> None:
        self._buffer.clear()
        self._decompressor.reset()

    def feed(self, data: bytes) -> list[TibiaPacket]:
        self._buffer.extend(data)
        packets: list[TibiaPacket] = []

        while len(self._buffer) >= PACKET_HEADER_SIZE:
            block_count = int.from_bytes(self._buffer[0:2], "little")
            sequence = int.from_bytes(self._buffer[2:4], "little")
            compression_flag = int.from_bytes(self._buffer[4:6], "little")

            if block_count == 0 or compression_flag not in VALID_COMPRESSION_FLAGS:
                logger.debug("Dropping invalid Tibia frame header; resynchronizing.")
                del self._buffer[0]
                continue

            frame_size = PACKET_HEADER_SIZE + block_count * XTEA_BLOCK_SIZE

            if len(self._buffer) < frame_size:
                break

            encrypted_payload = bytes(self._buffer[PACKET_HEADER_SIZE:frame_size])
            del self._buffer[:frame_size]
            packets.append(
                self._decode_packet(
                    sequence=sequence,
                    compressed=compression_flag == PACKET_COMPRESSED_FLAG,
                    encrypted_payload=encrypted_payload,
                )
            )

        return packets

    def _decode_packet(self, sequence: int, compressed: bool, encrypted_payload: bytes) -> TibiaPacket:
        if self._cipher is None:
            return TibiaPacket(
                from_client=self._from_client,
                sequence=sequence,
                compressed=compressed,
                decrypted=False,
                payload=encrypted_payload,
                encrypted_payload=encrypted_payload,
            )

        decrypted = self._cipher.decrypt(encrypted_payload)
        padding = decrypted[0]

        if padding > XTEA_BLOCK_SIZE - 1:
            raise TibiaProtocolError(f"Invalid XTEA padding byte: {padding}")

        payload = decrypted[1 : len(decrypted) - padding] if padding else decrypted[1:]

        if compressed:
            try:
                payload = self._decompressor.decompress(payload)
            except TibiaDecompressionError as error:
                raise TibiaProtocolError(str(error)) from error

        return TibiaPacket(
            from_client=self._from_client,
            sequence=sequence,
            compressed=compressed,
            decrypted=True,
            payload=payload,
            encrypted_payload=encrypted_payload,
        )
