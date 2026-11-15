from __future__ import annotations

import logging
from typing import Final

from cipfried.analysis.errors import ParseError, TruncatedMessage
from cipfried.analysis.opcodes import ServerOpcode
from cipfried.analysis.parser import MessageParser
from cipfried.analysis.reader import ByteReader
from cipfried.game.creature import Creature
from cipfried.game.item import Item
from cipfried.game.messages import FullMap
from cipfried.game.position import Position
from cipfried.game.tile import MAP_HEIGHT, MAP_WIDTH, Tile, tile_position_from_index

logger = logging.getLogger(__name__)

TILES_PER_FLOOR: Final[int] = MAP_WIDTH * MAP_HEIGHT  # 18 * 14 = 252
EXPECTED_NEXT_OPCODE: Final[int] = 0x78
CREATURE_FLAG: Final[bytes] = b"\x61\x00"
TILE_END_FLAG: Final[int] = 0xFF
MAX_CREATURE_NAME_LEN: Final[int] = 64


def expected_floors(pz: int) -> int:
    """Number of floors sent in the full map description packet."""
    return 8 if pz <= 7 else min(15, pz + 2) - (pz - 2) + 1


class FullMapParser(MessageParser):
    """Decodes full map message (opcode 0x64)."""

    opcode: int = ServerOpcode.FULL_MAP

    def parse(self, reader: ByteReader) -> FullMap:
        start_pos = reader.position
        if reader.remaining < 5:
            logger.debug(
                "Buffer too short for header at offset %d (remaining %d < 5)",
                start_pos,
                reader.remaining,
            )
            raise TruncatedMessage("Payload ended before FullMap position header")

        player_pos = Position(x=reader.read_u16(), y=reader.read_u16(), z=reader.read_u8())
        floors = expected_floors(player_pos.z)
        expected_tiles = TILES_PER_FLOOR * floors

        tiles_seen = 0
        tiles: list[Tile] = []

        while tiles_seen < expected_tiles:
            tile_start_offset = reader.position
            current_pos = tile_position_from_index(player_pos, tiles_seen)
            tile, skip = self._read_tile(reader, current_pos)

            tiles.append(tile)
            old_seen = tiles_seen
            tiles_seen += 1 + skip

            if logger.isEnabledFor(logging.DEBUG):
                has_content = tile.ground_id is not None or bool(tile.items) or bool(tile.creatures)
                if has_content or skip > 0:
                    logger.debug(
                        "Tile %d/%d at %s (offset %d): ground=%s, items=%d, creatures=%d, skip=%d -> tiles_seen=%d",
                        old_seen,
                        expected_tiles,
                        current_pos,
                        tile_start_offset,
                        f"0x{tile.ground_id:04X}" if tile.ground_id is not None else "None",
                        len(tile.items),
                        len(tile.creatures),
                        skip,
                        tiles_seen,
                    )

            if tiles_seen > expected_tiles:
                logger.debug(
                    "Overshot: tiles_seen=%d > expected_tiles=%d (skip=%d) at offset %d",
                    tiles_seen,
                    expected_tiles,
                    skip,
                    reader.position,
                )
                raise ParseError(
                    f"Tile count overshot expected total: {tiles_seen} > {expected_tiles} "
                    f"(skip count {skip} at offset {reader.position})"
                )

        if tiles_seen != expected_tiles:
            logger.debug(
                "Tile mismatch: tiles_seen=%d != expected_tiles=%d at offset %d",
                tiles_seen,
                expected_tiles,
                reader.position,
            )
            raise ParseError(f"Tile count mismatch: seen {tiles_seen} != expected {expected_tiles}")

        logger.debug(
            "Completed: parsed %d tiles (%d non-empty) for player at %s; reader at offset %d, %d bytes remaining",
            len(tiles),
            sum(1 for t in tiles if t.ground_id is not None or t.items or t.creatures),
            player_pos,
            reader.position,
            reader.remaining,
        )

        if not reader.eof:
            next_op = reader.peek_u8()
            if next_op != EXPECTED_NEXT_OPCODE:
                logger.warning(
                    "Soft check warning: next opcode after FullMap is 0x%02X at offset %d, expected 0x%02X",
                    next_op,
                    reader.position,
                    EXPECTED_NEXT_OPCODE,
                )
            else:
                logger.debug(
                    "Soft check passed: next opcode is 0x%02X at offset %d",
                    next_op,
                    reader.position,
                )

        return FullMap(opcode=self.opcode, player_position=player_pos, tiles=tuple(tiles))

    def _read_tile(self, reader: ByteReader, position: Position) -> tuple[Tile, int]:
        tile = Tile(position=position)
        skip = 0

        while True:
            if reader.remaining < 2:
                logger.debug(
                    "Truncated reading tile at %s (offset %d, remaining %d < 2)",
                    position,
                    reader.position,
                    reader.remaining,
                )
                raise TruncatedMessage(f"Buffer ended unexpectedly while reading tile at offset {reader.position}")

            next_two = reader.peek_bytes(2)

            if next_two[1] == TILE_END_FLAG:
                skip = next_two[0]
                reader.skip(2)
                break

            if next_two == CREATURE_FLAG:
                creature = self._read_creature(reader, position)
                tile.add_creature(creature)
                continue

            # Otherwise, item or ground ID
            item_id = reader.read_u16()

            if tile.ground_id is None and not tile.items:
                tile.ground_id = item_id
            else:
                tile.add_item(Item(id=item_id))

        return tile, skip

    def _read_creature(self, reader: ByteReader, position: Position) -> Creature:
        creature_start_offset = reader.position
        if reader.remaining < 6:
            raise TruncatedMessage("Buffer ended before creature header")
        reader.skip(6)

        # 4 bytes creature_id + 1 byte creature_type + 2 bytes name length = 7 bytes
        if reader.remaining < 7:
            raise TruncatedMessage("Buffer ended before creature identifier and name length")

        creature_id = reader.read_u32()
        creature_type = reader.read_u8()

        name_len = reader.read_u16()

        if name_len > MAX_CREATURE_NAME_LEN:
            logger.debug(
                "Implausible creature name length %d at offset %d (max: %d)",
                name_len,
                reader.position - 2,
                MAX_CREATURE_NAME_LEN,
            )
            raise ParseError(f"Implausible creature name length {name_len} at offset {reader.position - 2}")

        if reader.remaining < name_len:
            raise TruncatedMessage(f"Buffer ended before reading creature name ({name_len} bytes needed)")

        creature_name = reader.read_bytes(name_len).decode("utf-8", errors="replace")

        # 1 byte health + 1 byte dir + 11 bytes outfit + 2 bytes speed + 10 bytes flags = 25 bytes
        if reader.remaining < 25:
            raise TruncatedMessage(f"Buffer ended before reading creature attributes ({reader.remaining} < 25 bytes)")

        health_percentage = reader.read_u8()
        facing_dir = reader.read_u8()

        reader.skip(11)

        creature_speed = reader.read_u16()

        reader.skip(10)

        creature = Creature(
            id=creature_id,
            name=creature_name,
            creature_type=creature_type,
            health_percentage=health_percentage,
            facing_dir=facing_dir,
            speed=creature_speed,
            position=position,
        )

        logger.debug(
            "Parsed creature at %s (offset %d): id=0x%08X (%d), name=%r, type=%d, hp=%d%%, speed=%d, dir=%d",
            position,
            creature_start_offset,
            creature_id,
            creature_id,
            creature_name,
            creature_type,
            health_percentage,
            creature_speed,
            facing_dir,
        )

        return creature


__all__ = ["FullMapParser", "expected_floors"]
