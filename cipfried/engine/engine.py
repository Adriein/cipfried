import time

import keyboard

from cipfried.os import Process, Memory, Video
from cipfried.shared import EngineState, EngineCommand


class Engine:
    def __init__(self):
        self._game = Process(Memory(), Video())
        self._state = None

    def start(self):
        self._state = EngineState.Running

        self._set_stop_handler()

        self._game.hook()

        while self._game.pid is None:
            print("Tibia is not running...")

            self._game.hook()

            time.sleep(0.5)

        # video_stream = self._game.capture_video()

        while self._state is EngineState.Running:
            time.sleep(0.01)


        print("cipfried engine stopped.")

    def _set_stop_handler(self):
        keyboard.add_hotkey(EngineCommand.Stop.value, self._shutdown)

    def _shutdown(self):
        print(f"The {EngineCommand.Stop.value} key was pressed. Stopping cipfried engine...")
        self._state = EngineState.Stopped
