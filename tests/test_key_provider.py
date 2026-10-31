import pytest

from cipfried.network.key_provider import XteaKeyProvider
from cipfried.network.xtea import (
    XTEA_KEY_ANCHOR,
    XTEA_KEY_ANCHOR_DISTANCE,
    XTEA_KEY_OFFSET,
    XteaKey,
    find_xtea_key,
    find_xtea_key_addresses,
)
from tests.helpers import KEY, OTHER_KEY


class FakeProcess:
    def __init__(self, pid: int | None, anchors: list[int], keys: dict[int, XteaKey]) -> None:
        self.pid = pid
        self.anchors = anchors
        self.keys = keys
        self.scan_count = 0
        self.fail_reads = False

    def scan_memory(self, pattern: bytes) -> list[int]:
        assert pattern == XTEA_KEY_ANCHOR
        self.scan_count += 1
        return list(self.anchors)

    def read_memory(self, address: int, size: int) -> bytes:
        if self.fail_reads:
            raise OSError("stale address")

        key = self.keys.get(address)

        if key is None:
            raise OSError("unknown address")

        return key.to_bytes()[:size]


def anchors_for(key_address: int) -> tuple[int, int]:
    second_anchor = key_address + XTEA_KEY_OFFSET
    return second_anchor - XTEA_KEY_ANCHOR_DISTANCE, second_anchor


def test_finds_all_key_addresses() -> None:
    first_anchors = anchors_for(1136)
    second_anchors = anchors_for(2136)
    process = FakeProcess(1, [*first_anchors, *second_anchors], {})

    assert find_xtea_key_addresses(process) == [1136, 2136]


def test_find_xtea_key_uses_last_candidate() -> None:
    first_anchors = anchors_for(1136)
    second_anchors = anchors_for(2136)
    process = FakeProcess(1, [*first_anchors, *second_anchors], {1136: KEY, 2136: OTHER_KEY})

    assert find_xtea_key(process) == OTHER_KEY


def test_provider_caches_addresses_but_reads_current_key() -> None:
    first_anchors = anchors_for(1136)
    second_anchors = anchors_for(2136)
    process = FakeProcess(1, [*first_anchors, *second_anchors], {1136: KEY, 2136: OTHER_KEY})
    provider = XteaKeyProvider()

    assert provider.candidates(process) == [KEY, OTHER_KEY]
    assert process.scan_count == 1

    process.keys[1136] = OTHER_KEY

    assert provider.candidates(process) == [OTHER_KEY]
    assert process.scan_count == 1


def test_provider_rescans_when_cached_reads_fail() -> None:
    first_anchors = anchors_for(1136)
    process = FakeProcess(1, list(first_anchors), {1136: KEY})
    provider = XteaKeyProvider()
    provider.candidates(process)

    second_anchors = anchors_for(2136)
    process.anchors = list(second_anchors)
    process.keys = {2136: OTHER_KEY}
    process.fail_reads = True

    original_read = process.read_memory

    def read_after_rescan(address: int, size: int) -> bytes:
        if process.fail_reads and process.scan_count > 1:
            process.fail_reads = False

        return original_read(address, size)

    process.read_memory = read_after_rescan  # type: ignore[method-assign]

    assert provider.candidates(process) == [OTHER_KEY]
    assert process.scan_count == 2


def test_provider_can_force_rescan() -> None:
    first_anchors = anchors_for(1136)
    process = FakeProcess(1, list(first_anchors), {1136: KEY})
    provider = XteaKeyProvider()
    provider.candidates(process)

    process.anchors = list(anchors_for(2136))
    process.keys = {2136: OTHER_KEY}

    assert provider.candidates(process, force_rescan=True) == [OTHER_KEY]
    assert process.scan_count == 2


def test_provider_resets_on_pid_change() -> None:
    first_anchors = anchors_for(1136)
    process = FakeProcess(1, list(first_anchors), {1136: KEY})
    provider = XteaKeyProvider()
    provider.candidates(process)

    process.pid = 2
    process.anchors = list(anchors_for(2136))
    process.keys = {2136: OTHER_KEY}

    assert provider.candidates(process) == [OTHER_KEY]
    assert process.scan_count == 2


def test_provider_rejects_unhooked_process() -> None:
    provider = XteaKeyProvider()
    process = FakeProcess(None, [], {})

    with pytest.raises(RuntimeError):
        provider.candidates(process)


def test_missing_anchor_raises() -> None:
    process = FakeProcess(1, [], {})

    with pytest.raises(ValueError):
        find_xtea_key_addresses(process)
