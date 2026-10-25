import logging

from cipfried.os.memory import Memory

logger = logging.getLogger(__name__)


class Process:
    def __init__(self, memory: Memory, name: str = "Tibia") -> None:
        self._memory = memory
        self._pids: list[int] = []

        self.name = name
        self.pid: int | None = None

    @property
    def pids(self) -> list[int]:
        return list(self._pids)

    def hook(self) -> None:
        self._pids = self._memory.get_pids_by_name(self.name)
        self.pid = self._pids[0] if self._pids else None

        if len(self._pids) > 1:
            logger.warning(
                "Multiple %s processes found (%s); using PID %s.",
                self.name,
                self._pids,
                self.pid,
            )

    def is_alive(self) -> bool:
        return self.pid is not None and self._memory.is_process_alive(self.pid)

    def read_memory(self, address: int, size: int) -> bytes:
        return self._memory.read(self._hooked_pid(), address, size)

    def scan_memory(self, pattern: bytes) -> list[int]:
        return self._memory.scan(self._hooked_pid(), pattern)

    def _hooked_pid(self) -> int:
        if self.pid is None:
            raise RuntimeError(f"{self.name} process is not hooked")

        if not self._memory.is_process_alive(self.pid):
            raise RuntimeError(f"{self.name} process {self.pid} is no longer running")

        return self.pid
