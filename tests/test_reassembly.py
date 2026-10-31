from cipfried.network.reassembly import TcpReassembler


def test_in_order_segments() -> None:
    reassembler = TcpReassembler()

    assert reassembler.feed(100, b"hello ") == b"hello "
    assert reassembler.feed(106, b"world") == b"world"


def test_out_of_order_segments() -> None:
    reassembler = TcpReassembler()

    assert reassembler.feed(100, b"hello ") == b"hello "
    assert reassembler.feed(112, b"!") == b""
    assert reassembler.feed(106, b"world") == b"world"
    assert reassembler.feed(111, b"?") == b"?!"


def test_duplicate_and_overlapping_segments() -> None:
    reassembler = TcpReassembler()

    assert reassembler.feed(100, b"hello world") == b"hello world"
    assert reassembler.feed(100, b"hello world") == b""
    assert reassembler.feed(105, b" world!!!") == b"!!!"


def test_sequence_wraparound() -> None:
    reassembler = TcpReassembler()

    assert reassembler.feed(0xFFFFFFF8, b"A" * 8) == b"A" * 8
    assert reassembler.feed(0x00000000, b"B" * 8) == b"B" * 8


def test_out_of_order_across_wraparound() -> None:
    reassembler = TcpReassembler()

    assert reassembler.feed(0xFFFFFFF8, b"A" * 8) == b"A" * 8
    assert reassembler.feed(0x00000008, b"C" * 8) == b""
    assert reassembler.feed(0x00000000, b"B" * 8) == b"B" * 8 + b"C" * 8


def test_pending_overflow_recovers(monkeypatch: object) -> None:
    reassembler = TcpReassembler()
    monkeypatch.setattr(TcpReassembler, "MAX_PENDING_BYTES", 16)  # type: ignore[attr-defined]

    assert reassembler.feed(100, b"A" * 10) == b"A" * 10
    assert reassembler.feed(200, b"B" * 10) == b""
    assert reassembler.feed(300, b"C" * 10) == b"B" * 10
    assert reassembler.feed(210, b"D" * 90) == b"D" * 90 + b"C" * 10


def test_reset_clears_state() -> None:
    reassembler = TcpReassembler()

    reassembler.feed(100, b"A" * 8)
    reassembler.feed(120, b"C" * 8)
    reassembler.reset()

    assert reassembler.feed(500, b"fresh") == b"fresh"
