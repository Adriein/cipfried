import logging
import time
from typing import Final, Protocol

from cipfried.network.xtea import (
    XTEA_KEY_SIZE,
    MemoryProcess,
    XteaKey,
    find_xtea_key_addresses,
)

logger = logging.getLogger(__name__)

RESCAN_INTERVAL: Final = 30.0


class KeyProcess(MemoryProcess, Protocol):
    @property
    def pid(self) -> int | None: ...


class XteaKeyProvider:
    """Reads XTEA key candidates while caching their addresses per process."""

    def __init__(self) -> None:
        self._pid: int | None = None
        self._addresses: tuple[int, ...] = ()
        self._last_scan = 0.0

    def reset(self) -> None:
        self._pid = None
        self._addresses = ()
        self._last_scan = 0.0

    def candidates(self, process: KeyProcess, *, force_rescan: bool = False) -> list[XteaKey]:
        pid = process.pid

        if pid is None:
            raise RuntimeError("Process is not hooked")

        if pid != self._pid:
            self.reset()
            self._pid = pid

        now = time.monotonic()

        if force_rescan or not self._addresses or now - self._last_scan >= RESCAN_INTERVAL:
            self._addresses = tuple(find_xtea_key_addresses(process))
            self._last_scan = now

        keys, failed = self._read_keys(process)

        if failed and not keys:
            logger.debug("Cached XTEA addresses are stale; rescanning process memory.")
            self._addresses = tuple(find_xtea_key_addresses(process))
            self._last_scan = now
            keys, _ = self._read_keys(process)

        return keys

    def _read_keys(self, process: KeyProcess) -> tuple[list[XteaKey], bool]:
        keys: list[XteaKey] = []
        failed = False

        for address in self._addresses:
            try:
                raw = process.read_memory(address, XTEA_KEY_SIZE)
                key = XteaKey.from_bytes(raw)
            except (OSError, RuntimeError, ValueError):
                failed = True
                continue

            if key not in keys:
                keys.append(key)

        return keys, failed
