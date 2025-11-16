import os

class Memory:
    ModeReadOnly = 'r'

    def get_pid_by_name(self, name: str) -> int|None:
        for pid in os.listdir('/proc'):
            if not pid.isdigit():
                continue

            try:
                with open(os.path.join('/proc', pid, 'cmdline'), self.ModeReadOnly) as buff:
                    if name in buff.read().strip():
                        return int(pid)

            except (IOError, FileNotFoundError):
                continue

        return None

