import zlib

from cipfried.network.protocol import TibiaStreamDecoder
from cipfried.network.xtea import XteaCipher
from tests.helpers import make_frame, make_frame_from_encoded


def test_decodes_consecutive_frames(cipher: XteaCipher) -> None:
    decoder = TibiaStreamDecoder(cipher, from_client=False)
    data = make_frame(cipher, 1, b"one") + make_frame(cipher, 2, b"two")

    packets = decoder.feed(data)

    assert [packet.sequence for packet in packets] == [1, 2]
    assert [packet.payload for packet in packets] == [b"one", b"two"]
    assert all(packet.decrypted for packet in packets)
    assert decoder.stats.frames == 2


def test_decodes_incremental_chunks(cipher: XteaCipher) -> None:
    decoder = TibiaStreamDecoder(cipher, from_client=False)
    data = make_frame(cipher, 1, b"one") + make_frame(cipher, 2, b"two")
    packets = []

    for byte in data:
        packets.extend(decoder.feed(bytes([byte])))

    assert [packet.payload for packet in packets] == [b"one", b"two"]


def test_decodes_all_padding_values(cipher: XteaCipher) -> None:
    decoder = TibiaStreamDecoder(cipher, from_client=False)
    payloads = [b"x" * (7 - padding) for padding in range(8)]
    data = b"".join(
        make_frame(cipher, sequence, payload)
        for sequence, payload in enumerate(payloads, start=1)
    )

    packets = decoder.feed(data)

    assert [packet.payload for packet in packets] == payloads


def test_buffers_before_cipher_and_replays(cipher: XteaCipher) -> None:
    decoder = TibiaStreamDecoder(None, from_client=False)
    data = make_frame(cipher, 1, b"one") + make_frame(cipher, 2, b"two")

    assert decoder.feed(data) == []

    decoder.set_cipher(cipher)

    assert [packet.payload for packet in decoder.feed(b"")] == [b"one", b"two"]


def test_waits_for_second_frame_before_syncing(cipher: XteaCipher) -> None:
    decoder = TibiaStreamDecoder(cipher, from_client=False)
    first = make_frame(cipher, 1, b"one")
    second = make_frame(cipher, 2, b"two")

    assert decoder.feed(first) == []
    assert [packet.payload for packet in decoder.feed(second)] == [b"one", b"two"]
    assert [packet.payload for packet in decoder.feed(make_frame(cipher, 3, b"three"))] == [b"three"]


def test_resynchronizes_after_garbage(cipher: XteaCipher) -> None:
    decoder = TibiaStreamDecoder(cipher, from_client=False)
    data = b"\xaa\xbb\xcc" + make_frame(cipher, 1, b"one") + make_frame(cipher, 2, b"two")

    assert [packet.payload for packet in decoder.feed(data)] == [b"one", b"two"]


def test_key_change_resets_stream(cipher: XteaCipher, other_cipher: XteaCipher) -> None:
    decoder = TibiaStreamDecoder(cipher, from_client=False)
    decoder.feed(make_frame(cipher, 1, b"one") + make_frame(cipher, 2, b"two"))

    decoder.set_cipher(other_cipher)

    assert decoder.stats.frames == 0
    assert [packet.payload for packet in decoder.feed(make_frame(other_cipher, 1, b"new"))] == []
    assert [packet.payload for packet in decoder.feed(make_frame(other_cipher, 2, b"key"))] == [b"new", b"key"]


def test_drops_only_failed_compressed_frame(cipher: XteaCipher) -> None:
    decoder = TibiaStreamDecoder(cipher, from_client=False)
    invalid = make_frame_from_encoded(cipher, 1, b"\xff\xff\xff\xff", compressed=True)
    valid = make_frame(cipher, 2, b"valid")

    packets = decoder.feed(invalid + valid)

    assert [packet.payload for packet in packets] == [b"valid"]
    assert decoder.stats.dropped == 1
    assert decoder.stats.decompression_failures == 1


def test_decompresses_stateful_stream(cipher: XteaCipher) -> None:
    decoder = TibiaStreamDecoder(cipher, from_client=False)
    encoder = zlib.compressobj(wbits=-15)
    data = make_frame(cipher, 1, b"hello ", compressed=True, encoder=encoder)
    data += make_frame(cipher, 2, b"world", compressed=True, encoder=encoder)

    packets = decoder.feed(data)

    assert [packet.payload for packet in packets] == [b"hello ", b"world"]


def test_matches_cipher_requires_complete_frames(cipher: XteaCipher, other_cipher: XteaCipher) -> None:
    decoder = TibiaStreamDecoder(None, from_client=False)
    decoder.feed(make_frame(cipher, 1, b"one"))
    assert not decoder.matches_cipher(cipher)

    decoder.feed(make_frame(cipher, 2, b"two"))
    assert decoder.matches_cipher(cipher)
    assert not decoder.matches_cipher(other_cipher)


def test_rejects_consumed_key_change_without_cipher(cipher: XteaCipher) -> None:
    decoder = TibiaStreamDecoder(cipher, from_client=False)
    decoder.feed(make_frame(cipher, 1, b"one") + make_frame(cipher, 2, b"two"))

    decoder.set_cipher(None)

    assert decoder.stats.frames == 0
    assert decoder.feed(make_frame(cipher, 3, b"three")) == []
