
from cipfried.analysis.opcodes import ServerOpcode
from cipfried.analysis.parser import MessageParser
from cipfried.analysis.reader import ByteReader
from cipfried.game.messages import LoginSuccess


class FullMapParser(MessageParser):
    """Decodes full map message.

    The pipeline consumes the opcode before calling ``parse``. Fill in the
    field reads you already worked out; the reader must be advanced by exactly
    the bytes this message owns so the pipeline can continue with the rest of
    the payload.
    """

    opcode: int = ServerOpcode.FULL_MAP

    def parse(self, reader: ByteReader) -> LoginSuccess:
        player_id = reader.read_u32()

        return LoginSuccess(opcode=self.opcode, player_id=player_id)
