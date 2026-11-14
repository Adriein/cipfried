from dataclasses import dataclass

import pytest

from cipfried.analysis import ByteReader, MessagePipeline, TruncatedMessage
from cipfried.analysis.errors import ParseError
from cipfried.analysis.parsers.full_map import FullMapParser, expected_floors
from cipfried.game import FullMap, GameMessage, Position
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


def test_expected_floors() -> None:
    # Surface and above: always 8 floors
    assert expected_floors(7) == 8
    assert expected_floors(0) == 8

    # Underground: z-2 to min(15, z+2)
    # z=8: floors 6 to 10 -> 5 floors
    assert expected_floors(8) == 5
    # z=13: floors 11 to 15 -> 5 floors
    assert expected_floors(13) == 5
    # z=14: floors 12 to 15 -> 4 floors
    assert expected_floors(14) == 4
    # z=15: floors 13 to 15 -> 3 floors
    assert expected_floors(15) == 3


def test_full_map_parser_valid_skipped_map() -> None:
    # Player at (32000, 32000, 7) -> 8 floors -> 2016 tiles
    header = (32000).to_bytes(2, "little") + (32000).to_bytes(2, "little") + bytes([7])

    # 8 floors of 252 tiles skipped: 1 + 251 = 252 per floor
    skips = bytes([251, 0xFF]) * 8

    # Next opcode is 0x78 (inventory slot)
    payload = header + skips + b"\x78\x01\x02"

    reader = ByteReader(payload)
    parser = FullMapParser()
    msg = parser.parse(reader)

    assert isinstance(msg, FullMap)
    assert msg.player_position == Position(32000, 32000, 7)
    assert msg.tiles == ()  # All tiles were empty/skipped

    # Reader must be at offset where 0x78 begins
    assert reader.position == len(header) + len(skips)
    assert reader.peek_u8() == 0x78


def test_full_map_parser_with_items_and_creature() -> None:
    header = (32000).to_bytes(2, "little") + (32000).to_bytes(2, "little") + bytes([7])

    # Tile 0:
    # 1. Ground item: 0x0100 (256)
    ground = (0x0100).to_bytes(2, "little")
    # 2. Creature block: 0x61 0x00
    creature_header = b"\x61\x00\x00\x00\x00\x00"
    creature_id = (0x40000001).to_bytes(4, "little")
    creature_type = b"\x00"
    name = b"Rat"
    name_block = len(name).to_bytes(2, "little") + name
    creature_tail = bytes([100, 2]) + (b"\x00" * 11) + (110).to_bytes(2, "little") + (b"\x00" * 10)
    creature_data = creature_header + creature_id + creature_type + name_block + creature_tail

    # 3. Stacked item: 0x0200
    item = (0x0200).to_bytes(2, "little")

    # Tile 0 ends with skip=0 (no extra tiles skipped after tile 0)
    tile0_end = bytes([0, 0xFF])

    tile0_bytes = ground + creature_data + item + tile0_end

    # Remaining 2015 tiles:
    # 7 full floors of 252 tiles = 1764
    # and 251 tiles on the first floor
    remaining_skips = bytes([250, 0xFF]) + (bytes([251, 0xFF]) * 7)

    payload = header + tile0_bytes + remaining_skips + b"\x78"

    reader = ByteReader(payload)
    parser = FullMapParser()
    msg = parser.parse(reader)

    assert msg.player_position == Position(32000, 32000, 7)
    assert len(msg.tiles) == 1

    tile = msg.tiles[0]
    assert tile.position == Position(32000 - 8, 32000 - 6, 7)
    assert tile.ground_id == 0x0100
    assert len(tile.items) == 1
    assert tile.items[0].id == 0x0200
    assert len(tile.creatures) == 1
    assert tile.creatures[0].name == "Rat"
    assert tile.creatures[0].id == 0x40000001

    assert reader.peek_u8() == 0x78


def test_full_map_parser_overshoot_raises_parse_error() -> None:
    header = (32000).to_bytes(2, "little") + (32000).to_bytes(2, "little") + bytes([7])
    # 7 floors = 1764 tiles, plus a skip of 253 tiles (1 + 253 = 254) -> 2018 > 2016
    skips = (bytes([251, 0xFF]) * 7) + bytes([253, 0xFF])
    payload = header + skips

    reader = ByteReader(payload)
    parser = FullMapParser()
    with pytest.raises(ParseError, match="Tile count overshot"):
        parser.parse(reader)


def test_full_map_parser_premature_end_raises_truncated_message() -> None:
    header = (32000).to_bytes(2, "little") + (32000).to_bytes(2, "little") + bytes([7])
    # Only 1 floor (252 tiles) provided instead of expected 8 floors (2016 tiles)
    skips = bytes([251, 0xFF])
    payload = header + skips

    reader = ByteReader(payload)
    parser = FullMapParser()
    with pytest.raises(TruncatedMessage):
        parser.parse(reader)


def test_full_map_parser_implausible_item_id_raises_parse_error() -> None:
    header = (32000).to_bytes(2, "little") + (32000).to_bytes(2, "little") + bytes([7])
    # Item ID 0x0010 is below 0x67
    bad_item = (0x0010).to_bytes(2, "little")
    payload = header + bad_item

    reader = ByteReader(payload)
    parser = FullMapParser()
    with pytest.raises(ParseError, match="Implausible item ID"):
        parser.parse(reader)


def test_full_map_parser_truncated_buffer_raises_truncated_message() -> None:
    header = (32000).to_bytes(2, "little") + (32000).to_bytes(2, "little") + bytes([7])
    # Cut off immediately
    payload = header + b"\x01"

    reader = ByteReader(payload)
    parser = FullMapParser()
    with pytest.raises(TruncatedMessage):
        parser.parse(reader)


def test_full_map_parser_soft_check_warning(caplog: pytest.LogCaptureFixture) -> None:
    header = (32000).to_bytes(2, "little") + (32000).to_bytes(2, "little") + bytes([7])
    skips = bytes([251, 0xFF]) * 8
    # Next opcode is 0xAA instead of 0x78
    payload = header + skips + b"\xAA"

    reader = ByteReader(payload)
    parser = FullMapParser()
    import logging
    with caplog.at_level(logging.WARNING):
        parser.parse(reader)

    assert "expected 0x78" in caplog.text
