from dataclasses import dataclass

import pytest

from cipfried.analysis import ByteReader, MessagePipeline, TruncatedMessage
from cipfried.game import GameMessage
from cipfried.network.protocol import TibiaPacket


@dataclass(frozen=True)
class ValueMessage(GameMessage):
    value: int


class ValueParser:
    opcode = 0x42

    def parse(self, reader: ByteReader) -> ValueMessage:
        return ValueMessage(opcode=self.opcode, value=reader.read_u8())


class NoProgressParser:
    opcode = 0x43

    def parse(self, reader: ByteReader) -> ValueMessage:
        return ValueMessage(opcode=self.opcode, value=0)


class ShortParser:
    opcode = 0x44

    def parse(self, reader: ByteReader) -> ValueMessage:
        return ValueMessage(opcode=self.opcode, value=reader.read_u16())


def make_packet(payload: bytes, *, from_client: bool = False, decrypted: bool = True) -> TibiaPacket:
    return TibiaPacket(
        from_client=from_client,
        sequence=1,
        compressed=False,
        decrypted=decrypted,
        payload=payload,
        encrypted_payload=b"",
    )


def make_pipeline() -> MessagePipeline:
    pipeline = MessagePipeline()
    pipeline.register(ValueParser())
    pipeline.register(NoProgressParser())
    pipeline.register(ShortParser())
    return pipeline


def test_reader_reads_little_endian_values() -> None:
    reader = ByteReader(b"\x01\x02\x03\x04\x05\x06\x07")

    assert reader.read_u8() == 0x01
    assert reader.read_u16() == 0x0302
    assert reader.read_u32() == 0x07060504
    assert reader.eof


def test_reader_raises_when_payload_is_truncated() -> None:
    reader = ByteReader(b"\x01")

    with pytest.raises(TruncatedMessage):
        reader.read_u16()


def test_pipeline_decodes_consecutive_messages() -> None:
    result = make_pipeline().feed_payload(b"\x42\x07\x42\x09")

    assert [message.value for message in result.messages] == [7, 9]
    assert result.consumed == 4
    assert result.remaining == b""
    assert result.stopped_at is None


def test_pipeline_stops_at_unknown_opcode_and_returns_remainder() -> None:
    result = make_pipeline().feed_payload(b"\x42\x07\x99\x01")

    assert [message.value for message in result.messages] == [7]
    assert result.consumed == 2
    assert result.remaining == b"\x99\x01"
    assert result.stopped_at == 0x99


def test_pipeline_rejects_parser_that_consumes_nothing() -> None:
    pipeline = make_pipeline()

    result = pipeline.feed_payload(b"\x43\x01")

    assert result.messages == ()
    assert result.consumed == 0
    assert result.remaining == b"\x43\x01"
    assert result.stopped_at == 0x43
    assert pipeline.stats.parse_errors == 1


def test_pipeline_stops_when_message_is_truncated() -> None:
    pipeline = make_pipeline()

    result = pipeline.feed_payload(b"\x44\x01")

    assert result.messages == ()
    assert result.consumed == 0
    assert result.remaining == b"\x44\x01"
    assert result.stopped_at == 0x44
    assert pipeline.stats.parse_errors == 1


def test_pipeline_ignores_client_and_encrypted_packets() -> None:
    pipeline = make_pipeline()

    assert pipeline.feed(make_packet(b"\x42\x07", from_client=True)).messages == ()
    assert pipeline.feed(make_packet(b"\x42\x07", decrypted=False)).messages == ()


def test_pipeline_notifies_listeners() -> None:
    seen: list[int] = []
    pipeline = make_pipeline()
    pipeline.add_listener(lambda message: seen.append(message.opcode))

    pipeline.feed(make_packet(b"\x42\x07"))

    assert seen == [0x42]
