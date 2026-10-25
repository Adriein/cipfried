import logging
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

    @property
    def is_running(self) -> bool:
        return self._sniffer is not None

    def set_handler(self, handler: Callable[[TibiaPacket], None] | None) -> None:
        self._on_packet = handler

    def set_cipher(self, cipher: XteaCipher | None) -> None:
        self._cipher = cipher

        for state in self._streams.values():
            state.decoder.set_cipher(cipher)

    def start(self, interface: str | None = None) -> None:
        if self._sniffer is not None:
            return

        sniffer = AsyncSniffer(
            iface=interface,
            filter=f"tcp port {self.TIBIA_SERVER_PORT}",
            prn=self._handle_packet,
            store=False,
        )
        sniffer.start()
        self._sniffer = sniffer
        logger.info("Sniffing Tibia traffic on TCP port %d.", self.TIBIA_SERVER_PORT)

    def stop(self) -> None:
        sniffer = self._sniffer
        self._sniffer = None

        if sniffer is not None:
            sniffer.stop()
            logger.info("Stopped Tibia packet sniffer.")

        self._streams.clear()

    def _handle_packet(self, packet: Any) -> None:
        tcp = packet.getlayer(TCP)

        if tcp is None or not packet.haslayer(Raw):
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
        state = self._streams.get(endpoint)

        if state is None:
            state = _StreamState(
                reassembler=TcpReassembler(),
                decoder=TibiaStreamDecoder(self._cipher, from_client),
            )
            self._streams[endpoint] = state
            logger.info("Capturing Tibia traffic %s:%d -> %s:%d.", *endpoint)

        try:
            stream = state.reassembler.feed(int(tcp.seq), bytes(packet[Raw].load))
            packets = state.decoder.feed(stream)
        except (TibiaProtocolError, ValueError) as error:
            logger.warning(
                "Resetting Tibia stream %s:%d -> %s:%d: %s", *endpoint, error
            )
            self._streams.pop(endpoint, None)
            return

        for tibia_packet in packets:
            self._dispatch(tibia_packet)

        if int(tcp.flags) & 0x05:
            self._streams.pop(endpoint, None)

    def _dispatch(self, packet: TibiaPacket) -> None:
        if self._on_packet is None:
            return

        try:
            self._on_packet(packet)
        except Exception:
            logger.exception("Tibia packet handler failed.")
