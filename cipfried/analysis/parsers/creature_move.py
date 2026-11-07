from cipfried.analysis.opcodes import ServerOpcode
from cipfried.analysis.parser import MessageParser
from cipfried.analysis.reader import ByteReader
from cipfried.game.messages import CreatureMovement
from cipfried.game.position import Position


class CreatureMoveParser(MessageParser):
    """Decodes a creature movement message.

    The pipeline consumes the opcode before calling ``parse``. Fill in the
    field reads you already worked out; the reader must be advanced by exactly
    the bytes this message owns so the pipeline can continue with the rest of
    the payload.
    """

    opcode: int = ServerOpcode.CREATURE_MOVE

    def parse(self, reader: ByteReader) -> CreatureMovement:
        old_pos = Position(x=reader.read_u16(), y=reader.read_u16(), z=reader.read_u8())
        stack = reader.read_u8()
        new_pos = Position(x=reader.read_u16(), y=reader.read_u16(), z=reader.read_u8())

        return CreatureMovement(opcode=self.opcode, old_position=old_pos, old_stackpos=stack, new_position=new_pos)
