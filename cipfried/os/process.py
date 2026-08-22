from cipfried.os.memory import Memory

class Process:
    def __init__(self, memory: Memory):
        self._memory = memory

        self.name = 'Tibia'
        self.pid = None

    def hook(self,) -> None:
        self.pid = self._memory.get_pid_by_name(self.name)