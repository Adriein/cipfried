import logging
import zlib
from typing import Final

logger = logging.getLogger(__name__)

PACKET_SYNC_FLUSH = b"\x00\x00\xff\xff"
DEFAULT_MAX_OUTPUT: Final = 16 * 1024 * 1024


class TibiaDecompressionError(ValueError):
    pass


class TibiaDecompressor:
    """Stateful raw-deflate decompressor for one Tibia stream direction."""

    def __init__(self, max_output: int = DEFAULT_MAX_OUTPUT) -> None:
        if max_output <= 0:
            raise ValueError("max_output must be positive")

        self._decompressor: zlib._Decompress | None = None
        self._max_output = max_output
        self.reset_count = 0
        self.eof_count = 0

    def decompress(self, data: bytes) -> bytes:
        data += PACKET_SYNC_FLUSH

        if self._decompressor is None:
            self._decompressor = zlib.decompressobj(wbits=-zlib.MAX_WBITS)

        try:
            result = self._decompressor.decompress(data, self._max_output)
        except zlib.error:
            logger.debug("Resetting Tibia decompression stream after zlib error.")
            self.reset_count += 1
            self._decompressor = zlib.decompressobj(wbits=-zlib.MAX_WBITS)

            try:
                result = self._decompressor.decompress(data, self._max_output)
            except zlib.error as error:
                raise TibiaDecompressionError("Invalid compressed Tibia payload") from error

        if self._decompressor.unconsumed_tail:
            self.reset()
            raise TibiaDecompressionError(f"Decompressed Tibia payload exceeds {self._max_output} bytes")

        if self._decompressor.eof:
            self._decompressor = None
            self.eof_count += 1

        return result

    def reset(self) -> None:
        self._decompressor = None
