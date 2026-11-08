
from cipfried.analysis.opcodes import ServerOpcode
from cipfried.analysis.parser import MessageParser
from cipfried.analysis.reader import ByteReader
from cipfried.game.messages import GameMessage


class WorldEnteredParser(MessageParser):
    """Decodes world entered message.

    The pipeline consumes the opcode before calling ``parse``. Fill in the
    field reads you already worked out; the reader must be advanced by exactly
    the bytes this message owns so the pipeline can continue with the rest of
    the payload.
    """

    opcode: int = ServerOpcode.WORLD_ENTERED

    def parse(self, reader: ByteReader) -> GameMessage:
        return GameMessage(opcode=self.opcode)
