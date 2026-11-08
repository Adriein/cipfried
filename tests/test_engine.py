from cipfried.core.engine import Engine
from cipfried.network.key_provider import XteaKeyProvider
from cipfried.network.protocol import TibiaPacket
from cipfried.network.xtea import (
    XTEA_KEY_ANCHOR,
    XTEA_KEY_ANCHOR_DISTANCE,
    XTEA_KEY_OFFSET,
    XteaCipher,
    XteaKey,
)
from tests.helpers import KEY, OTHER_KEY


class FakeProcess:
    def __init__(self, key: XteaKey = KEY, pid: int | None = 1) -> None:
        self.name = "Tibia"
        self.pid = pid
        self.key = key
        second_anchor = 1000 + XTEA_KEY_ANCHOR_DISTANCE
        self.key_address = second_anchor - XTEA_KEY_OFFSET
        self.anchors = [1000, second_anchor]
        self.extra_keys: dict[int, XteaKey] = {}
        self.scan_count = 0

    def scan_memory(self, pattern: bytes) -> list[int]:
        assert pattern == XTEA_KEY_ANCHOR
        self.scan_count += 1
        return self.anchors

    def read_memory(self, address: int, size: int) -> bytes:
        if address == self.key_address:
            return self.key.to_bytes()[:size]

        key = self.extra_keys.get(address)

        if key is None:
            raise OSError("unknown address")

        return key.to_bytes()[:size]


class FakeSniffer:
    def __init__(self) -> None:
        self.cipher: XteaCipher | None = None
        self.valid_key: XteaKey | None = None
        self.has_buffered = False
        self.handler = None

    def set_handler(self, handler: object) -> None:
        self.handler = handler

    def set_cipher(self, cipher: XteaCipher | None) -> None:
        self.cipher = cipher

    def validate_cipher(self, cipher: XteaCipher) -> bool:
        if self.valid_key is None:
            return False

        probe = b"12345678"
        return cipher.encrypt(probe) == XteaCipher(self.valid_key).encrypt(probe)

    def has_buffered_server_data(self) -> bool:
        return self.has_buffered


def test_refresh_loads_first_candidate_without_frames() -> None:
    process = FakeProcess()
    sniffer = FakeSniffer()
    engine = Engine(process=process, sniffer=sniffer)  # type: ignore[arg-type]

    engine._refresh_cipher()

    assert engine._xtea_key == KEY
    assert sniffer.cipher is not None


def test_refresh_switches_to_validated_candidate() -> None:
    process = FakeProcess()
    sniffer = FakeSniffer()
    engine = Engine(process=process, sniffer=sniffer)  # type: ignore[arg-type]
    engine._refresh_cipher()
    assert engine._xtea_key == KEY

    process.key = OTHER_KEY
    sniffer.valid_key = OTHER_KEY
    engine._refresh_cipher()

    assert engine._xtea_key == OTHER_KEY


def test_refresh_force_rescans_when_buffered_data_rejects_current_key() -> None:
    process = FakeProcess()
    sniffer = FakeSniffer()
    engine = Engine(process=process, sniffer=sniffer)  # type: ignore[arg-type]
    engine._refresh_cipher()
    assert process.scan_count == 1

    second_anchor = 2000 + XTEA_KEY_ANCHOR_DISTANCE
    new_address = second_anchor - XTEA_KEY_OFFSET
    process.anchors = [*process.anchors, 2000, second_anchor]
    process.extra_keys[new_address] = OTHER_KEY
    sniffer.has_buffered = True
    sniffer.valid_key = OTHER_KEY

    engine._refresh_cipher()

    assert process.scan_count == 2
    assert engine._xtea_key == OTHER_KEY


def test_refresh_keeps_valid_current_key_not_found_in_memory() -> None:
    process = FakeProcess(OTHER_KEY)
    sniffer = FakeSniffer()
    sniffer.valid_key = KEY
    engine = Engine(process=process, sniffer=sniffer)  # type: ignore[arg-type]
    engine._xtea_key = KEY
    sniffer.cipher = XteaCipher(KEY)

    engine._refresh_cipher()

    assert engine._xtea_key == KEY
    assert sniffer.cipher is not None
    assert sniffer.cipher.encrypt(b"12345678") == XteaCipher(KEY).encrypt(b"12345678")


def test_refresh_does_nothing_without_hooked_process() -> None:
    process = FakeProcess(pid=None)
    sniffer = FakeSniffer()
    engine = Engine(process=process, sniffer=sniffer)  # type: ignore[arg-type]

    engine._refresh_cipher()

    assert engine._xtea_key is None
    assert sniffer.cipher is None


class RecordingPipeline:
    def __init__(self) -> None:
        self.packets: list[TibiaPacket] = []

    def feed(self, packet: TibiaPacket) -> None:
        self.packets.append(packet)


def test_engine_process_packet_forwards_to_message_pipeline() -> None:
    pipeline = RecordingPipeline()
    engine = Engine(process=FakeProcess(), sniffer=FakeSniffer(), message_pipeline=pipeline)  # type: ignore[arg-type]
    packet = TibiaPacket(
        from_client=False,
        sequence=1,
        compressed=False,
        decrypted=True,
        payload=b"\x42\x07",
        encrypted_payload=b"",
    )

    engine._process_packet(packet)

    assert pipeline.packets == [packet]


def test_engine_on_packet_enqueues_packet() -> None:
    engine = Engine(process=FakeProcess(), sniffer=FakeSniffer())  # type: ignore[arg-type]
    packet = TibiaPacket(
        from_client=False,
        sequence=1,
        compressed=False,
        decrypted=True,
        payload=b"\x42\x07",
        encrypted_payload=b"",
    )

    engine._on_packet(packet)

    assert engine._packet_queue.get_nowait() == packet


def test_engine_on_packet_drops_when_queue_full() -> None:
    engine = Engine(process=FakeProcess(), sniffer=FakeSniffer(), packet_queue_size=1)  # type: ignore[arg-type]
    packet1 = TibiaPacket(
        from_client=False,
        sequence=1,
        compressed=False,
        decrypted=True,
        payload=b"\x42\x07",
        encrypted_payload=b"",
    )
    packet2 = TibiaPacket(
        from_client=False,
        sequence=2,
        compressed=False,
        decrypted=True,
        payload=b"\x42\x08",
        encrypted_payload=b"",
    )

    engine._on_packet(packet1)
    # Should not raise queue.Full
    engine._on_packet(packet2)

    assert engine._packet_queue.get_nowait() == packet1
    assert engine._packet_queue.empty()


def test_engine_pipeline_worker_processes_queued_packets() -> None:
    pipeline = RecordingPipeline()
    engine = Engine(process=FakeProcess(), sniffer=FakeSniffer(), message_pipeline=pipeline)  # type: ignore[arg-type]
    packet = TibiaPacket(
        from_client=False,
        sequence=1,
        compressed=False,
        decrypted=True,
        payload=b"\x42\x07",
        encrypted_payload=b"",
    )

    engine._start_pipeline_worker()
    try:
        engine._on_packet(packet)
        engine._packet_queue.join()
        assert pipeline.packets == [packet]
    finally:
        engine._stop_pipeline_worker()


def test_engine_pipeline_worker_handles_exception_gracefully() -> None:
    class FailingPipeline:
        def __init__(self) -> None:
            self.calls = 0

        def feed(self, packet: TibiaPacket) -> None:
            self.calls += 1
            raise RuntimeError("Parser failure")

    pipeline = FailingPipeline()
    engine = Engine(process=FakeProcess(), sniffer=FakeSniffer(), message_pipeline=pipeline)  # type: ignore[arg-type]
    packet = TibiaPacket(
        from_client=False,
        sequence=1,
        compressed=False,
        decrypted=True,
        payload=b"\x42\x07",
        encrypted_payload=b"",
    )

    engine._start_pipeline_worker()
    try:
        engine._on_packet(packet)
        engine._packet_queue.join()
        assert pipeline.calls == 1
        assert engine._pipeline_thread is not None
        assert engine._pipeline_thread.is_alive()
    finally:
        engine._stop_pipeline_worker()


def test_key_provider_reset_clears_cached_pid() -> None:
    provider = XteaKeyProvider()
    process = FakeProcess()

    provider.candidates(process)  # type: ignore[arg-type]
    assert provider._pid == 1

    provider.reset()

    assert provider._pid is None
    assert provider._addresses == ()
