import logging
import threading
import time
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
ServerEndpoint = tuple[str, int]

TCP_FIN: Final = 0x01
TCP_SYN: Final = 0x02
TCP_RST: Final = 0x04
TCP_STREAM_END_FLAGS: Final = TCP_FIN | TCP_RST

ACTIVE_TIMEOUT: Final = 10.0
SERVER_CONFIRM_PACKETS: Final = 2
MAX_PENDING_PACKETS: Final = 256


@dataclass
class _StreamState:
    reassembler: TcpReassembler
    decoder: TibiaStreamDecoder
    from_client: bool
    server_endpoint: ServerEndpoint
    last_seen: float
    last_decoded: float = 0.0


class TibiaSniffer:
    TIBIA_SERVER_PORT: Final = 7171

    def __init__(
        self,
        on_packet: Callable[[TibiaPacket], None] | None = None,
        *,
        interface: str | None = None,
        server_port: int = TIBIA_SERVER_PORT,
        bpf_filter: str | None = None,
    ) -> None:
        self._on_packet = on_packet
        self._cipher: XteaCipher | None = None
        self._sniffer: AsyncSniffer | None = None
        self._streams: dict[TcpEndpoint, _StreamState] = {}
        self._pending_packets: dict[ServerEndpoint, list[TibiaPacket]] = {}
        self._active_server: ServerEndpoint | None = None
        self._lock = threading.Lock()
        self._interface = interface
        self._server_port = server_port
        self._bpf_filter = bpf_filter if bpf_filter is not None else f"tcp port {server_port}"

    @property
    def is_running(self) -> bool:
        return self._sniffer is not None

    def set_handler(self, handler: Callable[[TibiaPacket], None] | None) -> None:
        with self._lock:
            self._on_packet = handler

    def set_cipher(self, cipher: XteaCipher | None) -> None:
        decoded: list[tuple[ServerEndpoint, bool, list[TibiaPacket]]] = []
        packets: list[TibiaPacket] = []
        now = time.monotonic()

        with self._lock:
            if cipher is self._cipher:
                return

            self._cipher = cipher
            self._active_server = None
            self._pending_packets.clear()

            for state in self._streams.values():
                state.decoder.set_cipher(cipher)
                state.last_decoded = 0.0

                if cipher is not None:
                    state_packets = state.decoder.feed(b"")

                    if state_packets:
                        state.last_decoded = now
                        decoded.append((state.server_endpoint, state.from_client, state_packets))

            if cipher is not None:
                self._active_server = self._choose_initial_server()

                if self._active_server is not None:
                    for server_endpoint, _, state_packets in decoded:
                        if server_endpoint == self._active_server:
                            packets.extend(state_packets)
                else:
                    for server_endpoint, from_client, state_packets in decoded:
                        if not from_client:
                            self._buffer_pending(server_endpoint, state_packets)

        for packet in packets:
            self._dispatch(packet)

    def validate_cipher(self, cipher: XteaCipher, min_frames: int = 2) -> bool:
        with self._lock:
            return any(
                not state.from_client and state.decoder.matches_cipher(cipher, min_frames)
                for state in self._streams.values()
            )

    def has_buffered_server_data(self) -> bool:
        with self._lock:
            return any(
                not state.from_client and state.decoder.buffered_bytes > 0
                for state in self._streams.values()
            )

    def start(self, interface: str | None = None) -> None:
        with self._lock:
            if self._sniffer is not None:
                return

            sniffer = AsyncSniffer(
                iface=interface if interface is not None else self._interface,
                filter=self._bpf_filter,
                prn=self._handle_packet,
                store=False,
            )

            try:
                sniffer.start()
            except Exception as error:
                raise RuntimeError(f"Unable to start Tibia capture: {error}") from error

            self._sniffer = sniffer

        logger.info("Sniffing Tibia traffic on TCP port %d.", self._server_port)

    def stop(self) -> None:
        with self._lock:
            sniffer = self._sniffer
            self._sniffer = None
            self._streams.clear()
            self._pending_packets.clear()
            self._active_server = None

        if sniffer is not None:
            sniffer.stop()
            logger.info("Stopped Tibia packet sniffer.")

    def _handle_packet(self, packet: Any) -> None:
        tcp = packet.getlayer(TCP)

        if tcp is None:
            return

        if tcp.sport == self._server_port:
            from_client = False
        elif tcp.dport == self._server_port:
            from_client = True
        else:
            return

        ip = packet.getlayer(IP) or packet.getlayer(IPv6)

        if ip is None:
            return

        endpoint: TcpEndpoint = (ip.src, int(tcp.sport), ip.dst, int(tcp.dport))
        server_endpoint: ServerEndpoint = (
            (ip.dst, int(tcp.dport)) if from_client else (ip.src, int(tcp.sport))
        )
        flags = int(tcp.flags)
        stream_ended = bool(flags & TCP_STREAM_END_FLAGS)
        syn = bool(flags & TCP_SYN)
        now = time.monotonic()
        packets: list[TibiaPacket] = []

        with self._lock:
            if syn:
                self._streams.pop(endpoint, None)
                self._clear_active_server(server_endpoint)

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
                    from_client=from_client,
                    server_endpoint=server_endpoint,
                    last_seen=now,
                )
                self._streams[endpoint] = state
                logger.info("Capturing Tibia traffic %s:%d -> %s:%d.", *endpoint)

            state.last_seen = now
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
                self._clear_active_server(server_endpoint)
                return

            if packets:
                state.last_decoded = now

            logger.debug(
                "Tibia stream %s:%d -> %s:%d decoded %d packets from %d reassembled bytes.",
                *endpoint,
                len(packets),
                len(stream),
            )

            if not from_client and packets:
                if self._active_server is None:
                    self._buffer_pending(server_endpoint, packets)
                    self._select_server()
                    packets = self._take_pending(self._active_server) if self._active_server is not None else []
                else:
                    self._switch_server_if_needed(now)
                    packets = self._packets_to_dispatch(state, packets)
            else:
                packets = self._packets_to_dispatch(state, packets)

            if stream_ended:
                self._streams.pop(endpoint, None)
                self._clear_active_server(server_endpoint)

        for tibia_packet in packets:
            self._dispatch(tibia_packet)

    def _select_server(self) -> None:
        if self._active_server is not None:
            return

        best = self._best_server(SERVER_CONFIRM_PACKETS)

        if best is None:
            return

        self._active_server = best
        logger.info("Using Tibia server endpoint %s:%d.", *best)

    def _buffer_pending(self, server_endpoint: ServerEndpoint, packets: list[TibiaPacket]) -> None:
        pending = self._pending_packets.setdefault(server_endpoint, [])
        pending.extend(packets)

        if len(pending) > MAX_PENDING_PACKETS:
            del pending[: len(pending) - MAX_PENDING_PACKETS]

    def _take_pending(self, server_endpoint: ServerEndpoint) -> list[TibiaPacket]:
        packets = self._pending_packets.pop(server_endpoint, [])
        self._pending_packets.clear()

        return packets

    def _switch_server_if_needed(self, now: float) -> None:
        if self._active_server is None:
            return

        decoded, _, last_decoded = self._server_health(self._active_server)

        if decoded > 0 and now - last_decoded <= ACTIVE_TIMEOUT:
            return

        best = self._best_server(SERVER_CONFIRM_PACKETS)

        if best is None or best == self._active_server:
            return

        logger.info("Switching Tibia server endpoint from %s:%d to %s:%d.", *self._active_server, *best)
        self._active_server = best

    def _choose_initial_server(self) -> ServerEndpoint | None:
        best = self._best_server(SERVER_CONFIRM_PACKETS)

        if best is not None:
            return best

        return self._best_server(1)

    def _best_server(self, min_decoded: int) -> ServerEndpoint | None:
        best: tuple[tuple[int, int, float], ServerEndpoint] | None = None

        for server_endpoint in {state.server_endpoint for state in self._streams.values()}:
            decoded, failures, last_decoded = self._server_health(server_endpoint)

            if decoded < min_decoded:
                continue

            score = (decoded, -failures, last_decoded)

            if best is None or score > best[0]:
                best = (score, server_endpoint)

        return best[1] if best is not None else None

    def _server_health(self, server_endpoint: ServerEndpoint) -> tuple[int, int, float]:
        decoded = 0
        failures = 0
        last_decoded = 0.0

        for state in self._streams.values():
            if state.server_endpoint != server_endpoint or state.from_client:
                continue

            stats = state.decoder.stats
            decoded += stats.frames
            failures += stats.padding_failures + stats.decompression_failures
            last_decoded = max(last_decoded, state.last_decoded)

        return decoded, failures, last_decoded

    def _packets_to_dispatch(self, state: _StreamState, packets: list[TibiaPacket]) -> list[TibiaPacket]:
        if not packets or self._active_server is None:
            return []

        if state.server_endpoint != self._active_server:
            return []

        return packets

    def _clear_active_server(self, server_endpoint: ServerEndpoint) -> None:
        if self._active_server == server_endpoint:
            self._active_server = None

        self._pending_packets.pop(server_endpoint, None)

    def _dispatch(self, packet: TibiaPacket) -> None:
        if self._on_packet is None:
            return

        try:
            self._on_packet(packet)
        except Exception:
            logger.exception("Tibia packet handler failed.")
