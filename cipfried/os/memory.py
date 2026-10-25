import errno
import os
from typing import BinaryIO, Final


class Memory:
    MODE_READ_ONLY: Final = "r"
    PROC_FS: Final = "/proc"
    CHUNK_SIZE: Final = 1024 * 1024

    def get_pid_by_name(self, name: str) -> int | None:
        for pid in os.listdir(self.PROC_FS):
            if not pid.isdigit():
                continue

            try:
                with open(os.path.join(self.PROC_FS, pid, "cmdline"), self.MODE_READ_ONLY) as buff:
                    if name in buff.read().strip():
                        return int(pid)

            except OSError:
                continue

        return None

    def read(self, pid: int, address: int, size: int) -> bytes:
        """Reads bytes from a process at the given address."""
        if size < 0:
            raise ValueError("size must be non-negative")

        with self._open(pid) as mem:
            data = self._read_at(mem, address, size)

        if len(data) != size:
            raise OSError(errno.EIO, f"Short read at {address:#x}: expected {size} bytes, got {len(data)}")

        return data

    def scan(self, pid: int, pattern: bytes) -> list[int]:
        """Finds every address of pattern in the readable memory of a process."""
        if not pattern:
            raise ValueError("pattern must not be empty")

        addresses: list[int] = []
        overlap = len(pattern) - 1

        with self._open(pid) as mem:
            for start, end in self._ranges(pid):
                position = start
                previous = b""

                while position < end:
                    size = min(self.CHUNK_SIZE, end - position)

                    try:
                        chunk = self._read_at(mem, position, size)
                    except OSError:
                        break

                    if not chunk:
                        break

                    data = previous + chunk
                    base = position - len(previous)
                    match = data.find(pattern)

                    while match >= 0:
                        addresses.append(base + match)
                        match = data.find(pattern, match + 1)

                    previous = data[-overlap:] if overlap else b""
                    position += len(chunk)

                    if len(chunk) < size:
                        break

        return addresses

    def _open(self, pid: int) -> BinaryIO:
        try:
            return open(os.path.join(self.PROC_FS, str(pid), "mem"), "rb", buffering=0)
        except PermissionError as error:
            raise PermissionError(
                error.errno,
                f"Cannot access process {pid} memory; check Linux ptrace access policy",
            ) from error

    def _ranges(self, pid: int) -> list[tuple[int, int]]:
        ranges: list[tuple[int, int]] = []

        with open(os.path.join(self.PROC_FS, str(pid), "maps"), encoding="utf-8") as maps:
            for line in maps:
                fields = line.split(None, 5)
                start, end = (int(value, 16) for value in fields[0].split("-"))

                if fields[1][0] != self.MODE_READ_ONLY:
                    continue

                ranges.append((start, end))

        return ranges

    @staticmethod
    def _read_at(mem: BinaryIO, address: int, size: int) -> bytes:
        mem.seek(address)

        return mem.read(size)
