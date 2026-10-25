from cipfried.os.memory import Memory


class Process:
    def __init__(self, memory: Memory):
        self._memory = memory

        self.name = 'Tibia'
        self.pid: int | None = None

    def hook(self,) -> None:
        self.pid = self._memory.get_pid_by_name(self.name)

    def read_memory(self, address: int, size: int) -> bytes:
        return self._memory.read(self._hooked_pid(), address, size)

    def scan_memory(self, pattern: bytes) -> list[int]:
        return self._memory.scan(self._hooked_pid(), pattern)

    def _hooked_pid(self) -> int:
        if self.pid is None:
            raise RuntimeError("Tibia process is not hooked")

        return self.pid
