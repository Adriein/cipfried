from typing import Protocol

from cipfried.analysis.reader import ByteReader
from cipfried.game.messages import GameMessage


class MessageParser(Protocol):
    """Decodes one message body after its opcode has already been consumed."""

    opcode: int

    def parse(self, reader: ByteReader) -> GameMessage:
        """Consume exactly this message's bytes and return the typed message."""
        ...


class ParserRegistry:
    def __init__(self) -> None:
        self._parsers: dict[int, MessageParser] = {}

    def register(self, parser: MessageParser) -> None:
        opcode = int(parser.opcode)

        if opcode in self._parsers:
            raise ValueError(f"A parser is already registered for opcode 0x{opcode:02X}")

        self._parsers[opcode] = parser

    def get(self, opcode: int) -> MessageParser | None:
        return self._parsers.get(opcode)

    def __contains__(self, opcode: int) -> bool:
        return opcode in self._parsers


__all__ = ["MessageParser", "ParserRegistry"]
