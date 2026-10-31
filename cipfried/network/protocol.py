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
MAX_PENDING_BYTES = 1024 * 1024


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
        if cipher is self._cipher:
            return

        if cipher is None:
            self._cipher = None
            self.reset()
            return

        if self._cipher is None:
            self._cipher = cipher
            self._decompressor.reset()
            self._synced = False
            return

        self._cipher = cipher
        self.reset()

    def reset(self) -> None:
        self._buffer.clear()
        self._decompressor.reset()
        self._synced = self._cipher is None

    @property
    def _direction(self) -> str:
        return "client" if self._from_client else "server"

    def feed(self, data: bytes) -> list[TibiaPacket]:
        self._buffer.extend(data)
        packets: list[TibiaPacket] = []
        offset = 0

        logger.debug(
            "Tibia %s stream fed %d bytes (synced=%s, buffered=%d, cipher=%s).",
            self._direction,
            len(data),
            self._synced,
            len(self._buffer),
            self._cipher is not None,
        )

        if self._cipher is None:
            if len(self._buffer) > MAX_PENDING_BYTES:
                del self._buffer[: len(self._buffer) - MAX_PENDING_BYTES]

            logger.debug(
                "Tibia %s stream buffering without XTEA key (%d bytes pending).",
                self._direction,
                len(self._buffer),
            )
            return []

        while True:
            if not self._synced and self._cipher is not None:
                if self._seek_sync(offset) is None:
                    offset = 0
                    break

                offset = 0

            if len(self._buffer) - offset < PACKET_HEADER_SIZE:
                logger.debug(
                    "Tibia %s stream waiting for header at offset %d (%d/%d bytes).",
                    self._direction,
                    offset,
                    len(self._buffer) - offset,
                    PACKET_HEADER_SIZE,
                )
                break

            block_count = int.from_bytes(self._buffer[offset : offset + 2], "little")
            sequence = int.from_bytes(self._buffer[offset + 2 : offset + 4], "little")
            compression_flag = int.from_bytes(self._buffer[offset + 4 : offset + 6], "little")

            if block_count == 0 or block_count > MAX_BLOCK_COUNT or compression_flag not in VALID_COMPRESSION_FLAGS:
                logger.debug(
                    "Tibia %s invalid header at offset %d (blocks=%d, sequence=%d, flag=%#x); resynchronizing.",
                    self._direction,
                    offset,
                    block_count,
                    sequence,
                    compression_flag,
                )
                self._synced = False
                offset += 1
                continue

            frame_size = PACKET_HEADER_SIZE + block_count * XTEA_BLOCK_SIZE

            if len(self._buffer) - offset < frame_size:
                logger.debug(
                    "Tibia %s stream waiting for frame at offset %d (%d/%d bytes, sequence=%d).",
                    self._direction,
                    offset,
                    len(self._buffer) - offset,
                    frame_size,
                    sequence,
                )
                break

            payload_start = offset + PACKET_HEADER_SIZE
            encrypted_payload = bytes(self._buffer[payload_start : offset + frame_size])

            try:
                packet = self._decode_packet(
                    sequence=sequence,
                    compressed=compression_flag == PACKET_COMPRESSED_FLAG,
                    encrypted_payload=encrypted_payload,
                )
            except TibiaDecompressionError as error:
                self._decompressor.reset()
                offset += frame_size
                self._synced = True
                logger.debug(
                    "Tibia %s compressed packet sequence=%d dropped: %s", self._direction, sequence, error
                )
                continue
            except TibiaProtocolError as error:
                logger.debug(
                    "Tibia %s packet sequence=%d rejected at offset %d: %s; resynchronizing.",
                    self._direction,
                    sequence,
                    offset,
                    error,
                )
                self._synced = False
                continue

            offset += frame_size
            self._synced = True
            packets.append(packet)

        if offset:
            del self._buffer[:offset]

        logger.debug(
            "Tibia %s stream produced %d packets (%d bytes buffered).",
            self._direction,
            len(packets),
            len(self._buffer),
        )

        return packets

    def _seek_sync(self, start: int) -> int | None:
        earliest_incomplete: int | None = None
        position = start

        logger.debug(
            "Seeking Tibia %s frame sync from offset %d (%d buffered bytes).",
            self._direction,
            start,
            len(self._buffer),
        )

        while len(self._buffer) - position >= PACKET_HEADER_SIZE:
            block_count = int.from_bytes(self._buffer[position : position + 2], "little")
            compression_flag = int.from_bytes(self._buffer[position + 4 : position + 6], "little")

            if block_count == 0 or block_count > MAX_BLOCK_COUNT or compression_flag not in VALID_COMPRESSION_FLAGS:
                position += 1
                continue

            frame_size = PACKET_HEADER_SIZE + block_count * XTEA_BLOCK_SIZE

            logger.debug(
                "Tibia %s sync candidate at %d (blocks=%d, flag=%#x, size=%d).",
                self._direction,
                position,
                block_count,
                compression_flag,
                frame_size,
            )

            if len(self._buffer) - position < frame_size:
                if earliest_incomplete is None:
                    earliest_incomplete = position

                logger.debug(
                    "Tibia %s sync candidate at %d is incomplete (%d/%d bytes).",
                    self._direction,
                    position,
                    len(self._buffer) - position,
                    frame_size,
                )
                position += 1
                continue

            if not self._has_valid_padding(position, frame_size):
                position += 1
                continue

            if position:
                del self._buffer[:position]
                logger.debug(
                    "Tibia %s stream resynchronized after discarding %d bytes.", self._direction, position
                )

            self._synced = True
            return 0

        cut = (
            earliest_incomplete
            if earliest_incomplete is not None
            else max(start, len(self._buffer) - (PACKET_HEADER_SIZE - 1))
        )

        if cut:
            del self._buffer[:cut]

        return None

    def _has_valid_padding(self, position: int, frame_size: int) -> bool:
        cipher = self._cipher

        if cipher is None:
            return True

        encrypted_payload = bytes(self._buffer[position + PACKET_HEADER_SIZE : position + frame_size])
        decrypted = cipher.decrypt(encrypted_payload)
        padding = decrypted[0]

        if padding > XTEA_BLOCK_SIZE - 1:
            logger.debug(
                "Tibia %s sync candidate at %d rejected: invalid padding byte %d (decrypted head=%s).",
                self._direction,
                position,
                padding,
                decrypted[:8].hex(),
            )
            return False

        logger.debug(
            "Tibia %s sync candidate at %d accepted: padding=%d (decrypted head=%s).",
            self._direction,
            position,
            padding,
            decrypted[:8].hex(),
        )
        return True

    def _decode_packet(self, sequence: int, compressed: bool, encrypted_payload: bytes) -> TibiaPacket:
        if self._cipher is None:
            logger.debug(
                "Tibia %s packet sequence=%d left unencrypted (%d bytes).",
                self._direction,
                sequence,
                len(encrypted_payload),
            )
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

        logger.debug(
            "Tibia %s packet sequence=%d decrypted: padding=%d, size=%d, compressed=%s, head=%s.",
            self._direction,
            sequence,
            padding,
            len(decrypted),
            compressed,
            decrypted[:8].hex(),
        )

        if padding > XTEA_BLOCK_SIZE - 1:
            logger.debug(
                "Tibia %s packet sequence=%d has invalid padding byte %d (decrypted head=%s); XTEA key may be wrong.",
                self._direction,
                sequence,
                padding,
                decrypted[:8].hex(),
            )
            raise TibiaProtocolError(f"Invalid XTEA padding byte: {padding}")

        payload = decrypted[1 : len(decrypted) - padding] if padding else decrypted[1:]

        if compressed:
            logger.debug(
                "Tibia %s packet sequence=%d decompressing %d bytes.", self._direction, sequence, len(payload)
            )
            payload = self._decompressor.decompress(payload)
            logger.debug(
                "Tibia %s packet sequence=%d inflated to %d bytes.", self._direction, sequence, len(payload)
            )

        return TibiaPacket(
            from_client=self._from_client,
            sequence=sequence,
            compressed=compressed,
            decrypted=True,
            payload=payload,
            encrypted_payload=encrypted_payload,
        )
