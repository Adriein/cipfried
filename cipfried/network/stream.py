import logging
from dataclasses import dataclass
from typing import Final

from cipfried.network.decompressor import (
    DEFAULT_MAX_OUTPUT,
    TibiaDecompressionError,
    TibiaDecompressor,
)
from cipfried.network.frame import (
    PACKET_HEADER_SIZE,
    FrameHeader,
    parse_header,
)
from cipfried.network.xtea import XTEA_BLOCK_SIZE, XteaCipher

logger = logging.getLogger(__name__)

MAX_PENDING_BYTES: Final = 1024 * 1024
SYNC_CONFIRM_FRAMES: Final = 2


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


@dataclass
class DecodeStats:
    frames: int = 0
    dropped: int = 0
    sync_scans: int = 0
    padding_failures: int = 0
    decompression_failures: int = 0


class TibiaStreamDecoder:
    def __init__(
        self,
        cipher: XteaCipher | None,
        from_client: bool,
        *,
        max_pending_bytes: int = MAX_PENDING_BYTES,
        max_decompressed_bytes: int = DEFAULT_MAX_OUTPUT,
    ) -> None:
        if max_pending_bytes <= 0:
            raise ValueError("max_pending_bytes must be positive")

        self._cipher = cipher
        self._from_client = from_client
        self._buffer = bytearray()
        self._decompressor = TibiaDecompressor(max_decompressed_bytes)
        self._synced = cipher is None
        self._max_pending_bytes = max_pending_bytes
        self._stats = DecodeStats()

    @property
    def stats(self) -> DecodeStats:
        return self._stats

    @property
    def buffered_bytes(self) -> int:
        return len(self._buffer)

    def set_cipher(self, cipher: XteaCipher | None) -> None:
        if cipher is self._cipher:
            return

        if cipher is None:
            self._cipher = None
            self.reset(reset_stats=True)
            return

        if self._cipher is None:
            self._cipher = cipher
            self._decompressor.reset()
            self._synced = False
            return

        self._cipher = cipher
        self.reset(reset_stats=True)

    def reset(self, *, reset_stats: bool = False) -> None:
        self._buffer.clear()
        self._decompressor.reset()
        self._synced = self._cipher is None

        if reset_stats:
            self._stats = DecodeStats()

    @property
    def _direction(self) -> str:
        return "client" if self._from_client else "server"

    def feed(self, data: bytes) -> list[TibiaPacket]:
        self._buffer.extend(data)
        packets: list[TibiaPacket] = []
        offset = 0

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "Tibia %s stream fed %d bytes (synced=%s, buffered=%d, cipher=%s).",
                self._direction,
                len(data),
                self._synced,
                len(self._buffer),
                self._cipher is not None,
            )

        if self._cipher is None:
            self._trim_pending()
            logger.debug(
                "Tibia %s stream buffering without XTEA key (%d bytes pending).",
                self._direction,
                len(self._buffer),
            )
            return []

        while True:
            if not self._synced:
                if not self._seek_sync(offset):
                    offset = 0
                    break

                offset = 0

            header = parse_header(self._buffer, offset)

            if header is None:
                if len(self._buffer) - offset < PACKET_HEADER_SIZE:
                    break

                logger.debug(
                    "Tibia %s invalid header at offset %d; resynchronizing.",
                    self._direction,
                    offset,
                )
                self._synced = False
                offset += 1
                continue

            if len(self._buffer) - offset < header.size:
                logger.debug(
                    "Tibia %s stream waiting for frame at offset %d (%d/%d bytes, sequence=%d).",
                    self._direction,
                    offset,
                    len(self._buffer) - offset,
                    header.size,
                    header.sequence,
                )
                break

            payload_start = offset + PACKET_HEADER_SIZE
            encrypted_payload = bytes(self._buffer[payload_start : offset + header.size])

            try:
                packet = self._decode_packet(header, encrypted_payload)
            except TibiaDecompressionError as error:
                self._stats.decompression_failures += 1
                self._stats.dropped += 1
                self._decompressor.reset()
                offset += header.size
                self._synced = True
                logger.debug(
                    "Tibia %s compressed packet sequence=%d dropped: %s",
                    self._direction,
                    header.sequence,
                    error,
                )
                continue
            except TibiaProtocolError as error:
                self._stats.padding_failures += 1
                self._stats.dropped += 1
                logger.debug(
                    "Tibia %s packet sequence=%d rejected at offset %d: %s; resynchronizing.",
                    self._direction,
                    header.sequence,
                    offset,
                    error,
                )
                self._synced = False
                continue

            offset += header.size
            self._synced = True
            self._stats.frames += 1
            packets.append(packet)

        if offset:
            del self._buffer[:offset]

        if not self._synced:
            self._trim_pending()

        logger.debug(
            "Tibia %s stream produced %d packets (%d bytes buffered).",
            self._direction,
            len(packets),
            len(self._buffer),
        )

        return packets

    def matches_cipher(self, cipher: XteaCipher, min_frames: int = SYNC_CONFIRM_FRAMES) -> bool:
        """Returns True when the buffer contains enough frames that decode with this cipher."""
        if min_frames <= 0:
            raise ValueError("min_frames must be positive")

        position = 0

        while len(self._buffer) - position >= PACKET_HEADER_SIZE:
            confirmed, _ = self._sync_candidate(position, cipher, min_frames)

            if confirmed:
                return True

            position += 1

        return False

    def _seek_sync(self, start: int) -> bool:
        if self._cipher is None:
            return False

        self._stats.sync_scans += 1
        earliest_incomplete: int | None = None
        position = start

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "Seeking Tibia %s frame sync from offset %d (%d buffered bytes).",
                self._direction,
                start,
                len(self._buffer),
            )

        while len(self._buffer) - position >= PACKET_HEADER_SIZE:
            header = parse_header(self._buffer, position)

            if header is None:
                position += 1
                continue

            confirmed, incomplete = self._sync_candidate(position, self._cipher, SYNC_CONFIRM_FRAMES)

            if confirmed:
                if position:
                    del self._buffer[:position]
                    logger.debug(
                        "Tibia %s stream resynchronized after discarding %d bytes.",
                        self._direction,
                        position,
                    )

                self._synced = True
                return True

            if incomplete and earliest_incomplete is None:
                earliest_incomplete = position

            position += 1

        if earliest_incomplete is not None:
            cut = earliest_incomplete
        else:
            cut = max(start, len(self._buffer) - (PACKET_HEADER_SIZE - 1))

        if cut:
            del self._buffer[:cut]

        return False

    def _sync_candidate(
        self,
        position: int,
        cipher: XteaCipher,
        frames: int,
    ) -> tuple[bool, bool]:
        """Returns whether the candidate is confirmed and whether it needs more data."""
        if frames <= 0:
            raise ValueError("frames must be positive")

        header = parse_header(self._buffer, position)

        if header is None:
            return False, False

        if len(self._buffer) - position < header.size:
            return False, True

        if not self._padding_matches(position, header.size, cipher):
            return False, False

        next_position = position + header.size

        for _ in range(frames - 1):
            next_header = parse_header(self._buffer, next_position)

            if next_header is None:
                if len(self._buffer) - next_position < PACKET_HEADER_SIZE:
                    return False, True

                return False, False

            if len(self._buffer) - next_position < next_header.size:
                return False, True

            if not self._padding_matches(next_position, next_header.size, cipher):
                return False, False

            next_position += next_header.size

        return True, False

    def _padding_matches(self, position: int, frame_size: int, cipher: XteaCipher) -> bool:
        encrypted_payload = bytes(self._buffer[position + PACKET_HEADER_SIZE : position + frame_size])
        decrypted = cipher.decrypt(encrypted_payload)
        padding = decrypted[0]

        if padding > XTEA_BLOCK_SIZE - 1:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(
                    "Tibia %s sync candidate at %d rejected: invalid padding byte %d (decrypted head=%s).",
                    self._direction,
                    position,
                    padding,
                    decrypted[:8].hex(),
                )
            return False

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "Tibia %s sync candidate at %d accepted: padding=%d (decrypted head=%s).",
                self._direction,
                position,
                padding,
                decrypted[:8].hex(),
            )
        return True

    def _decode_packet(self, header: FrameHeader, encrypted_payload: bytes) -> TibiaPacket:
        cipher = self._cipher

        if cipher is None:
            raise RuntimeError("Cannot decode a Tibia packet without a cipher")

        decrypted = cipher.decrypt(encrypted_payload)
        padding = decrypted[0]

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "Tibia %s packet sequence=%d decrypted: padding=%d, size=%d, compressed=%s, head=%s.",
                self._direction,
                header.sequence,
                padding,
                len(decrypted),
                header.compressed,
                decrypted[:8].hex(),
            )

        if padding > XTEA_BLOCK_SIZE - 1:
            raise TibiaProtocolError(f"Invalid XTEA padding byte: {padding}")

        payload = decrypted[1 : len(decrypted) - padding] if padding else decrypted[1:]

        if header.compressed:
            logger.debug(
                "Tibia %s packet sequence=%d decompressing %d bytes.",
                self._direction,
                header.sequence,
                len(payload),
            )
            payload = self._decompressor.decompress(payload)
            logger.debug(
                "Tibia %s packet sequence=%d inflated to %d bytes.",
                self._direction,
                header.sequence,
                len(payload),
            )

        return TibiaPacket(
            from_client=self._from_client,
            sequence=header.sequence,
            compressed=header.compressed,
            decrypted=True,
            payload=payload,
            encrypted_payload=encrypted_payload,
        )

    def _trim_pending(self) -> None:
        if len(self._buffer) <= self._max_pending_bytes:
            return

        excess = len(self._buffer) - self._max_pending_bytes
        del self._buffer[:excess]
        logger.warning("Tibia %s pending buffer exceeded %d bytes; dropping oldest data.",
                       self._direction, self._max_pending_bytes)
