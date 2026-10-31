import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Final

from scapy.layers.inet import IP, TCP
from scapy.layers.inet6 import IPv6
from scapy.packet import Raw
from scapy.sendrecv import AsyncSniffer

from cipfried.network.protocol import (
    TibiaPacket,
    TibiaProtocolError,
    TibiaStreamDecoder,
)
from cipfried.network.reassembly import TcpReassembler
from cipfried.network.xtea import XteaCipher

logger = logging.getLogger(__name__)

TcpEndpoint = tuple[str, int, str, int]

TCP_FIN: Final = 0x01
TCP_RST: Final = 0x04
TCP_STREAM_END_FLAGS: Final = TCP_FIN | TCP_RST


@dataclass
class _StreamState:
    reassembler: TcpReassembler
    decoder: TibiaStreamDecoder


class TibiaSniffer:
    TIBIA_SERVER_PORT: Final = 7171

    def __init__(self, on_packet: Callable[[TibiaPacket], None] | None = None) -> None:
        self._on_packet = on_packet
        self._cipher: XteaCipher | None = None
        self._sniffer: AsyncSniffer | None = None
        self._streams: dict[TcpEndpoint, _StreamState] = {}
        self._active_server: tuple[str, int] | None = None
        self._lock = threading.Lock()

    @property
    def is_running(self) -> bool:
        return self._sniffer is not None

    def set_handler(self, handler: Callable[[TibiaPacket], None] | None) -> None:
        with self._lock:
            self._on_packet = handler

    def set_cipher(self, cipher: XteaCipher | None) -> None:
        packets: list[TibiaPacket] = []

        with self._lock:
            if cipher is self._cipher:
                return

            self._cipher = cipher
            self._active_server = None

            for state in self._streams.values():
                state.decoder.set_cipher(cipher)

            if cipher is not None:
                for state in self._streams.values():
                    packets.extend(state.decoder.feed(b""))

        for packet in packets:
            self._dispatch(packet)

    def start(self, interface: str | None = None) -> None:
        with self._lock:
            if self._sniffer is not None:
                return

        sniffer = AsyncSniffer(
            iface=interface,
            filter=f"tcp port {self.TIBIA_SERVER_PORT}",
            prn=self._handle_packet,
            store=False,
        )
        sniffer.start()

        with self._lock:
            self._sniffer = sniffer

        logger.info("Sniffing Tibia traffic on TCP port %d.", self.TIBIA_SERVER_PORT)

    def stop(self) -> None:
        with self._lock:
            sniffer = self._sniffer
            self._sniffer = None
            self._streams.clear()
            self._active_server = None

        if sniffer is not None:
            sniffer.stop()
            logger.info("Stopped Tibia packet sniffer.")

    def _handle_packet(self, packet: Any) -> None:
        tcp = packet.getlayer(TCP)

        if tcp is None:
            return

        if tcp.sport == self.TIBIA_SERVER_PORT:
            from_client = False
        elif tcp.dport == self.TIBIA_SERVER_PORT:
            from_client = True
        else:
            return

        ip = packet.getlayer(IP) or packet.getlayer(IPv6)

        if ip is None:
            return

        endpoint: TcpEndpoint = (ip.src, int(tcp.sport), ip.dst, int(tcp.dport))
        stream_ended = bool(int(tcp.flags) & TCP_STREAM_END_FLAGS)
        server_endpoint = (ip.dst, int(tcp.dport)) if from_client else (ip.src, int(tcp.sport))
        packets: list[TibiaPacket] = []

        with self._lock:
            if self._active_server is not None and server_endpoint != self._active_server:
                logger.debug(
                    "Ignoring Tibia stream %s:%d -> %s:%d; active server is %s:%d.",
                    *endpoint,
                    *self._active_server,
                )

                if stream_ended:
                    self._streams.pop(endpoint, None)

                return

            if not packet.haslayer(Raw):
                if stream_ended:
                    self._streams.pop(endpoint, None)
                    self._clear_active_server(server_endpoint)

                return

            state = self._streams.get(endpoint)

            if state is None:
                state = _StreamState(
                    reassembler=TcpReassembler(),
                    decoder=TibiaStreamDecoder(self._cipher, from_client),
                )
                self._streams[endpoint] = state
                logger.info("Capturing Tibia traffic %s:%d -> %s:%d.", *endpoint)

            raw_payload = bytes(packet[Raw].load)
            logger.debug(
                "Tibia stream %s:%d -> %s:%d raw segment seq=%d (%d bytes).",
                *endpoint,
                int(tcp.seq),
                len(raw_payload),
            )

            try:
                stream = state.reassembler.feed(int(tcp.seq), raw_payload)
                packets = state.decoder.feed(stream)
            except (TibiaProtocolError, ValueError) as error:
                logger.warning("Resetting Tibia stream %s:%d -> %s:%d: %s", *endpoint, error)
                self._streams.pop(endpoint, None)
                return

            logger.debug(
                "Tibia stream %s:%d -> %s:%d decoded %d packets from %d reassembled bytes.",
                *endpoint,
                len(packets),
                len(stream),
            )

            if not from_client and self._active_server is None and any(
                tibia_packet.decrypted for tibia_packet in packets
            ):
                self._active_server = server_endpoint
                logger.info(
                    "Using Tibia server endpoint %s:%d; ignoring other server streams.",
                    *server_endpoint,
                )

            if stream_ended:
                self._streams.pop(endpoint, None)
                self._clear_active_server(server_endpoint)

        for tibia_packet in packets:
            self._dispatch(tibia_packet)

    def _clear_active_server(self, server_endpoint: tuple[str, int]) -> None:
        if self._active_server == server_endpoint:
            self._active_server = None

    def _dispatch(self, packet: TibiaPacket) -> None:
        if self._on_packet is None:
            return

        try:
            self._on_packet(packet)
        except Exception:
            logger.exception("Tibia packet handler failed.")
