import logging
from collections.abc import Callable
from dataclasses import dataclass

from cipfried.analysis.errors import ParseError
from cipfried.analysis.parser import MessageParser, ParserRegistry
from cipfried.analysis.reader import ByteReader
from cipfried.game.messages import GameMessage
from cipfried.network.protocol import TibiaPacket

logger = logging.getLogger(__name__)

MessageListener = Callable[[GameMessage], None]


@dataclass(frozen=True)
class PipelineResult:
    """Outcome of mapping one payload.

    ``remaining`` starts at the opcode that could not be decoded, so it can be
    inspected while adding new parsers. On a fully decoded payload it is empty.
    """

    messages: tuple[GameMessage, ...] = ()
    consumed: int = 0
    remaining: bytes = b""
    stopped_at: int | None = None


@dataclass
class PipelineStats:
    packets: int = 0
    messages: int = 0
    unknown_opcodes: int = 0
    parse_errors: int = 0


class MessagePipeline:
    """Maps opaque payload bytes to typed game messages.

    Parsing happens on the caller's thread (the capture thread). Keep parsers
    cheap and stateless; hand expensive work to a worker that reads the latest
    value from a ``LatestValue`` slot instead of building a backlog.
    """

    def __init__(self, *, on_message: MessageListener | None = None) -> None:
        self._registry = ParserRegistry()
        self._listeners: list[MessageListener] = []
        self._stats = PipelineStats()

        if on_message is not None:
            self._listeners.append(on_message)

    @property
    def stats(self) -> PipelineStats:
        return self._stats

    def register(self, parser: MessageParser) -> None:
        self._registry.register(parser)

    def add_listener(self, listener: MessageListener) -> None:
        self._listeners.append(listener)

    def feed(self, packet: TibiaPacket) -> PipelineResult:
        if not packet.decrypted or packet.from_client:
            return PipelineResult()

        return self.feed_payload(packet.payload)

    def feed_payload(self, payload: bytes) -> PipelineResult:
        self._stats.packets += 1
        reader = ByteReader(payload)
        messages: list[GameMessage] = []
        stopped_at: int | None = None
        consumed = 0

        while not reader.eof:
            start = reader.position
            opcode = reader.read_u8()
            parser = self._registry.get(opcode)

            if parser is None:
                self._stats.unknown_opcodes += 1
                stopped_at = opcode
                consumed = start
                logger.debug(
                    "No parser for server opcode 0x%02X at offset %d; leaving the rest unparsed.",
                    opcode,
                    start,
                )
                break

            try:
                message = parser.parse(reader)
            except ParseError:
                self._stats.parse_errors += 1
                stopped_at = opcode
                consumed = start
                logger.debug("Failed to parse opcode 0x%02X at offset %d.", opcode, start, exc_info=True)
                break
            except Exception:
                self._stats.parse_errors += 1
                stopped_at = opcode
                consumed = start
                logger.exception("Unexpected failure parsing opcode 0x%02X at offset %d.", opcode, start)
                break

            if reader.position <= start + 1:
                self._stats.parse_errors += 1
                stopped_at = opcode
                consumed = start
                logger.warning("Parser for opcode 0x%02X consumed no bytes; stopping.", opcode)
                break

            messages.append(message)
            self._stats.messages += 1
            consumed = reader.position

        result = PipelineResult(
            messages=tuple(messages),
            consumed=consumed,
            remaining=payload[consumed:],
            stopped_at=stopped_at,
        )

        for message in messages:
            self._notify(message)

        return result

    def _notify(self, message: GameMessage) -> None:
        for listener in self._listeners:
            try:
                listener(message)
            except Exception:
                logger.exception("Message listener failed for opcode 0x%02X.", message.opcode)


__all__ = ["MessageListener", "MessagePipeline", "PipelineResult", "PipelineStats"]
