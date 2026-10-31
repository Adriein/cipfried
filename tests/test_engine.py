from cipfried.core.engine import Engine
from cipfried.network.key_provider import XteaKeyProvider
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


def test_key_provider_reset_clears_cached_pid() -> None:
    provider = XteaKeyProvider()
    process = FakeProcess()

    provider.candidates(process)  # type: ignore[arg-type]
    assert provider._pid == 1

    provider.reset()

    assert provider._pid is None
    assert provider._addresses == ()
