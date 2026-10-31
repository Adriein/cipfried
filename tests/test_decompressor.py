import zlib

import pytest

from cipfried.network.decompressor import TibiaDecompressionError, TibiaDecompressor
from tests.helpers import compress_payload


def test_decompresses_sync_flushed_payload() -> None:
    payload = b"hello tibia " * 100
    decompressor = TibiaDecompressor()

    assert decompressor.decompress(compress_payload(payload)) == payload


def test_decompresses_consecutive_frames() -> None:
    encoder = zlib.compressobj(wbits=-15)
    decompressor = TibiaDecompressor()

    assert decompressor.decompress(compress_payload(b"first ", encoder)) == b"first "
    assert decompressor.decompress(compress_payload(b"second", encoder)) == b"second"


def test_finished_stream_resets_for_next_stream() -> None:
    encoder = zlib.compressobj(wbits=-15)
    finished = encoder.compress(b"finished") + encoder.flush(zlib.Z_FINISH)
    decompressor = TibiaDecompressor()

    assert decompressor.decompress(finished) == b"finished"
    assert decompressor.eof_count == 1
    assert decompressor.decompress(compress_payload(b"next")) == b"next"


def test_invalid_payload_raises_decompression_error() -> None:
    with pytest.raises(TibiaDecompressionError):
        TibiaDecompressor().decompress(b"\xff\xff\xff\xff")


def test_output_limit_is_enforced() -> None:
    encoder = zlib.compressobj(wbits=-15)
    compressed = compress_payload(b"A" * 10_000, encoder)
    decompressor = TibiaDecompressor(max_output=32)

    with pytest.raises(TibiaDecompressionError):
        decompressor.decompress(compressed)


def test_rejects_invalid_max_output() -> None:
    with pytest.raises(ValueError):
        TibiaDecompressor(max_output=0)
