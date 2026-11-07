
from cipfried.analysis.opcodes import ServerOpcode
from cipfried.analysis.parser import MessageParser
from cipfried.analysis.reader import ByteReader
from cipfried.game.messages import GameMessage


class OpenChannelParser(MessageParser):
    """Decodes open channel message.

    The pipeline consumes the opcode before calling ``parse``. Fill in the
    field reads you already worked out; the reader must be advanced by exactly
    the bytes this message owns so the pipeline can continue with the rest of
    the payload.
    """

    opcode: int = ServerOpcode.OPEN_CHANNEL

    def parse(self, reader: ByteReader) -> GameMessage:
        reader.skip(13)

        return GameMessage(opcode=self.opcode)
