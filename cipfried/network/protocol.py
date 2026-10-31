import logging
from dataclasses import dataclass

from cipfried.network.decompressor import TibiaDecompressionError, TibiaDecompressor
from cipfried.network.xtea import XTEA_BLOCK_SIZE, XteaCipher

logger = logging.getLogger(__name__)

PACKET_HEADER_SIZE = 6
PACKET_COMPRESSED_FLAG = 0xC000
VALID_COMPRESSION_FLAGS = frozenset((0, PACKET_COMPRESSED_FLAG))
MAX_FRAME_SIZE = 0x10000
MAX_BLOCK_COUNT = (MAX_FRAME_SIZE - PACKET_HEADER_SIZE) // XTEA_BLOCK_SIZE


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
        self._synced = cipher is None

    def set_cipher(self, cipher: XteaCipher | None) -> None:
        self._cipher = cipher
        self._synced = cipher is None

    def reset(self) -> None:
        self._buffer.clear()
        self._decompressor.reset()
        self._synced = self._cipher is None

    def feed(self, data: bytes) -> list[TibiaPacket]:
        self._buffer.extend(data)
        packets: list[TibiaPacket] = []
        offset = 0

        while True:
            if not self._synced and self._cipher is not None:
                if self._seek_sync(offset) is None:
                    offset = 0
                    break

                offset = 0

            if len(self._buffer) - offset < PACKET_HEADER_SIZE:
                break

            block_count = int.from_bytes(self._buffer[offset : offset + 2], "little")
            sequence = int.from_bytes(self._buffer[offset + 2 : offset + 4], "little")
            compression_flag = int.from_bytes(self._buffer[offset + 4 : offset + 6], "little")

            if (
                block_count == 0
                or block_count > MAX_BLOCK_COUNT
                or compression_flag not in VALID_COMPRESSION_FLAGS
            ):
                self._synced = False
                offset += 1
                continue

            frame_size = PACKET_HEADER_SIZE + block_count * XTEA_BLOCK_SIZE

            if len(self._buffer) - offset < frame_size:
                break

            payload_start = offset + PACKET_HEADER_SIZE
            encrypted_payload = bytes(self._buffer[payload_start : offset + frame_size])

            try:
                packet = self._decode_packet(
                    sequence=sequence,
                    compressed=compression_flag == PACKET_COMPRESSED_FLAG,
                    encrypted_payload=encrypted_payload,
                )
            except TibiaDecompressionError:
                self._decompressor.reset()
                offset += frame_size
                self._synced = True
                logger.debug("Dropping compressed Tibia frame that could not be inflated.")
                continue
            except TibiaProtocolError:
                self._synced = False
                continue

            offset += frame_size
            self._synced = True
            packets.append(packet)

        if offset:
            del self._buffer[:offset]

        return packets

    def _seek_sync(self, start: int) -> int | None:
        earliest_incomplete: int | None = None
        position = start

        while len(self._buffer) - position >= PACKET_HEADER_SIZE:
            block_count = int.from_bytes(self._buffer[position : position + 2], "little")
            compression_flag = int.from_bytes(self._buffer[position + 4 : position + 6], "little")

            if (
                block_count == 0
                or block_count > MAX_BLOCK_COUNT
                or compression_flag not in VALID_COMPRESSION_FLAGS
            ):
                position += 1
                continue

            frame_size = PACKET_HEADER_SIZE + block_count * XTEA_BLOCK_SIZE

            if len(self._buffer) - position < frame_size:
                if earliest_incomplete is None:
                    earliest_incomplete = position

                position += 1
                continue

            if not self._has_valid_padding(position, frame_size):
                position += 1
                continue

            if position:
                del self._buffer[:position]
                logger.debug("Tibia stream resynchronized after discarding %d bytes.", position)

            self._synced = True
            return 0

        cut = earliest_incomplete if earliest_incomplete is not None else max(
            start, len(self._buffer) - (PACKET_HEADER_SIZE - 1)
        )

        if cut:
            del self._buffer[:cut]

        return None

    def _has_valid_padding(self, position: int, frame_size: int) -> bool:
        cipher = self._cipher

        if cipher is None:
            return True

        encrypted_payload = bytes(
            self._buffer[position + PACKET_HEADER_SIZE : position + frame_size]
        )
        decrypted = cipher.decrypt(encrypted_payload)

        return decrypted[0] <= XTEA_BLOCK_SIZE - 1

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
            payload = self._decompressor.decompress(payload)

        return TibiaPacket(
            from_client=self._from_client,
            sequence=sequence,
            compressed=compressed,
            decrypted=True,
            payload=payload,
            encrypted_payload=encrypted_payload,
        )
