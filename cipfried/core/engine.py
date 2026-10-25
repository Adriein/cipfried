import logging
import threading
import time
from collections.abc import Callable

import keyboard

from cipfried.core.constants import EngineCommand, GameState
from cipfried.core.context import Context, State
from cipfried.network.protocol import TibiaPacket
from cipfried.network.sniffer import TibiaSniffer
from cipfried.network.xtea import XteaCipher, find_xtea_key
from cipfried.os.memory import Memory
from cipfried.os.process import Process

logger = logging.getLogger(__name__)


class Engine:
    def __init__(self, process: Process | None = None, sniffer: TibiaSniffer | None = None) -> None:
        self._process = process if process is not None else Process(Memory())
        self._state = State()
        self._ctx = Context(game_state=self._state)
        self._stop_event = threading.Event()
        self._hotkey_handle: Callable[[], None] | None = None
        self._sniffer = sniffer if sniffer is not None else TibiaSniffer()
        self._sniffer.set_handler(self._on_packet)

    def start(self) -> None:
        if self._ctx.game_state.current != GameState.Stopped:
            logger.warning("Engine is already running or starting.")
            return

        self._stop_event.clear()
        self._ctx.game_state.current = GameState.Starting
        logger.info("Starting cipfried engine...")

        try:
            self._set_stop_handler()
            self._wait_for_process()

            if self._stop_event.is_set():
                return

            self._start_sniffer()

            if self._stop_event.is_set():
                return

            self._ctx.game_state.current = GameState.Running
            logger.info("cipfried engine running (PID: %s).", self._process.pid)
            self._monitor_process()
        finally:
            self._sniffer.stop()
            self._ctx.game_state.current = GameState.Stopped
            self._remove_stop_handler()
            logger.info("cipfried engine stopped.")

    def stop(self) -> None:
        if self._ctx.game_state.current == GameState.Stopped:
            return

        self._ctx.game_state.current = GameState.Stopping
        self._stop_event.set()

    def _wait_for_process(self, poll_interval: float = 0.5) -> None:
        self._process.hook()

        if self._process.pid is not None:
            logger.info("Hooked to %s process (PID: %s).", self._process.name, self._process.pid)
            return

        logger.info("%s is not running; waiting...", self._process.name)

        while not self._stop_event.is_set():
            time.sleep(poll_interval)
            self._process.hook()

            if self._process.pid is not None:
                logger.info("Hooked to %s process (PID: %s).", self._process.name, self._process.pid)
                return

    def _monitor_process(self, poll_interval: float = 1.0) -> None:
        while not self._stop_event.wait(poll_interval):
            if self._process.is_alive():
                continue

            logger.warning("%s process exited; waiting for restart...", self._process.name)
            self._sniffer.stop()
            self._ctx.game_state.current = GameState.Starting
            self._wait_for_process()

            if self._stop_event.is_set():
                return

            self._start_sniffer()

            if self._stop_event.is_set():
                return

            self._ctx.game_state.current = GameState.Running
            logger.info("cipfried engine running (PID: %s).", self._process.pid)

    def _start_sniffer(self) -> None:
        self._sniffer.set_cipher(self._load_cipher())
        self._sniffer.start()

    def _load_cipher(self) -> XteaCipher | None:
        logger.info("Searching for the XTEA key...")

        try:
            key = find_xtea_key(self._process)
        except (OSError, RuntimeError, ValueError) as error:
            logger.warning("XTEA key not found (%s); captured packets will remain encrypted.", error)
            return None

        logger.info("XTEA key loaded.")
        return XteaCipher(key)

    def _on_packet(self, packet: TibiaPacket) -> None:
        direction = "client" if packet.from_client else "server"

        if not packet.decrypted:
            logger.info(
                "%s seq=%d encrypted=%d bytes compressed=%s",
                direction,
                packet.sequence,
                len(packet.payload),
                packet.compressed,
            )
            return

        command = f"0x{packet.command:02X}" if packet.command is not None else "none"
        logger.info(
            "%s seq=%d cmd=%s len=%d compressed=%s",
            direction,
            packet.sequence,
            command,
            len(packet.payload),
            packet.compressed,
        )

        if packet.payload:
            logger.debug("%s payload: %s", direction, packet.payload[:128].hex(" "))

    def _set_stop_handler(self) -> None:
        if self._hotkey_handle is not None:
            return

        self._hotkey_handle = keyboard.add_hotkey(EngineCommand.Stop.value, self._on_stop_hotkey)

    def _remove_stop_handler(self) -> None:
        if self._hotkey_handle is None:
            return

        keyboard.remove_hotkey(self._hotkey_handle)
        self._hotkey_handle = None

    def _on_stop_hotkey(self) -> None:
        logger.info("Hotkey %s pressed.", EngineCommand.Stop.value)
        self.stop()
