import logging
import zlib

logger = logging.getLogger(__name__)

PACKET_SYNC_FLUSH = b"\x00\x00\xff\xff"


class TibiaDecompressionError(ValueError):
    pass


class TibiaDecompressor:
    """Stateful raw-deflate decompressor for one Tibia stream direction."""

    def __init__(self) -> None:
        self._decompressor: zlib._Decompress | None = None

    def decompress(self, data: bytes) -> bytes:
        data += PACKET_SYNC_FLUSH

        if self._decompressor is None:
            self._decompressor = zlib.decompressobj(wbits=-zlib.MAX_WBITS)

        try:
            result = self._decompressor.decompress(data)
        except zlib.error:
            logger.debug("Resetting Tibia decompression stream after zlib error.")
            self._decompressor = zlib.decompressobj(wbits=-zlib.MAX_WBITS)

            try:
                result = self._decompressor.decompress(data)
            except zlib.error as error:
                raise TibiaDecompressionError("Invalid compressed Tibia payload") from error

        if self._decompressor.eof:
            self._decompressor = None

        return result

    def reset(self) -> None:
        self._decompressor = None
