import logging
import threading
import time
from collections.abc import Callable

import keyboard

from cipfried.core.constants import EngineCommand, GameState
from cipfried.core.context import Context, State
from cipfried.network.key_provider import XteaKeyProvider
from cipfried.network.protocol import TibiaPacket
from cipfried.network.sniffer import TibiaSniffer
from cipfried.network.xtea import XteaCipher, XteaKey
from cipfried.os.memory import Memory
from cipfried.os.process import Process

logger = logging.getLogger(__name__)

KEY_POLL_INTERVAL = 5.0


class Engine:
    def __init__(self, process: Process | None = None, sniffer: TibiaSniffer | None = None) -> None:
        self._process = process if process is not None else Process(Memory())
        self._state = State()
        self._ctx = Context(game_state=self._state)
        self._stop_event = threading.Event()
        self._hotkey_handle: Callable[[], None] | None = None
        self._sniffer = sniffer if sniffer is not None else TibiaSniffer()
        self._sniffer.set_handler(self._on_packet)
        self._xtea_key: XteaKey | None = None
        self._key_provider = XteaKeyProvider()
        self._key_stop = threading.Event()
        self._key_thread: threading.Thread | None = None

    def start(self) -> None:
        if self._ctx.game_state.current != GameState.Stopped:
            logger.warning("Engine is already running or starting.")
            return

        self._stop_event.clear()
        self._key_stop.clear()
        self._ctx.game_state.current = GameState.Starting
        logger.info("Starting cipfried engine...")

        try:
            self._set_stop_handler()
            self._start_sniffer()
            self._start_key_watcher()
            self._wait_for_process()

            if self._stop_event.is_set():
                return

            self._ctx.game_state.current = GameState.Running
            logger.info("cipfried engine running (PID: %s).", self._process.pid)
            self._monitor_process()
        finally:
            self._stop_key_watcher()
            self._xtea_key = None
            self._key_provider.reset()
            self._sniffer.set_cipher(None)
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
            self._xtea_key = None
            self._key_provider.reset()
            self._sniffer.set_cipher(None)
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
        self._sniffer.start()

    def _start_key_watcher(self) -> None:
        if self._key_thread is not None:
            return

        self._key_thread = threading.Thread(target=self._watch_key, name="cipfried-xtea", daemon=True)
        self._key_thread.start()

    def _stop_key_watcher(self) -> None:
        self._key_stop.set()
        thread = self._key_thread
        self._key_thread = None

        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2.0)

    def _watch_key(self) -> None:
        logger.info("Watching for the XTEA key...")

        while not self._key_stop.is_set():
            self._refresh_cipher()
            self._key_stop.wait(KEY_POLL_INTERVAL)

    def _refresh_cipher(self) -> None:
        if self._key_stop.is_set() or self._process.pid is None:
            return

        current = self._xtea_key
        force_rescan = (
            current is not None
            and self._sniffer.has_buffered_server_data()
            and not self._sniffer.validate_cipher(XteaCipher(current))
        )

        try:
            candidates = self._key_provider.candidates(self._process, force_rescan=force_rescan)
        except (OSError, RuntimeError, ValueError) as error:
            logger.debug("XTEA key not available: %s", error)
            return

        key = self._select_key(candidates)

        if key is None or key == self._xtea_key:
            return

        changed = self._xtea_key is not None
        self._xtea_key = key
        self._sniffer.set_cipher(XteaCipher(key))
        logger.info("XTEA key %s.", "changed" if changed else "loaded")

    def _select_key(self, candidates: list[XteaKey]) -> XteaKey | None:
        if not candidates:
            return None

        current = self._xtea_key

        if current is not None and self._sniffer.validate_cipher(XteaCipher(current)):
            return current

        for candidate in candidates:
            if candidate == current:
                continue

            if self._sniffer.validate_cipher(XteaCipher(candidate)):
                return candidate

        if current is None or current not in candidates:
            return candidates[0]

        return current

    def _on_packet(self, packet: TibiaPacket) -> None:
        if not logger.isEnabledFor(logging.DEBUG):
            return

        direction = "client" if packet.from_client else "server"

        if not packet.decrypted:
            logger.debug(
                "%s seq=%d encrypted=%d bytes compressed=%s",
                direction,
                packet.sequence,
                len(packet.payload),
                packet.compressed,
            )
            return

        command = f"0x{packet.command:02X}" if packet.command is not None else "none"
        logger.debug(
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
