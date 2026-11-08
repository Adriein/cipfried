from cipfried.analysis.opcodes import ServerOpcode
from cipfried.analysis.parser import MessageParser
from cipfried.analysis.reader import ByteReader
from cipfried.game.messages import FullMap
from cipfried.game.position import Position


class FullMapParser(MessageParser):
    """Decodes full map message.

    The pipeline consumes the opcode before calling ``parse``. Fill in the
    field reads you already worked out; the reader must be advanced by exactly
    the bytes this message owns so the pipeline can continue with the rest of
    the payload.
    """

    X_AXIS_TILES = 14
    Y_AXIS_TILES = 18

    opcode: int = ServerOpcode.FULL_MAP

    def parse(self, reader: ByteReader) -> FullMap:
        player_pos = Position(x=reader.read_u16(), y=reader.read_u16(), z=reader.read_u8())

        while True:
            tile_id = reader.read_u16()

            next_two = reader.peek_bytes(2)

            skip_count = next_two[0]
            marker_flag = next_two[1]

            # We found the end marker
            if marker_flag == 0xff:
                reader.skip(skip_count+2)
                continue
            
            # We found a creature (always 38 bytes + name)
            if next_two == b"\x61\x00":
                # We skip 2 bytes for the marker + 4 of forget id
                reader.skip(6)

                creature_id = reader.read_u32()
                creature_type = reader.read_u8()
                creature_name = reader.read_string()
                health_percentage = reader.read_u8()
                facing_dir = reader.read_u8()

                reader.skip(11)

                creature_speed = reader.read_u16()
                
                reader.skip(10)


        return FullMap(opcode=self.opcode, player_position=player_pos)
