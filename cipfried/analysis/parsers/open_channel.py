from cipfried.analysis.opcodes import ServerOpcode
from cipfried.analysis.parser import MessageParser
from cipfried.analysis.reader import ByteReader
from cipfried.game.messages import OpenChannel


class OpenChannelParser(MessageParser):
    """Decodes open channel message.

    The pipeline consumes the opcode before calling ``parse``. Fill in the
    field reads you already worked out; the reader must be advanced by exactly
    the bytes this message owns so the pipeline can continue with the rest of
    the payload.
    """

    opcode: int = ServerOpcode.OPEN_CHANNEL

    def parse(self, reader: ByteReader) -> OpenChannel:
        chan_id = reader.read_u16()
        chan_name = reader.read_string()
        active_usr = reader.read_u16()
        invited_usr = reader.read_u16()

        return OpenChannel(
            opcode=self.opcode,
            channel_id=chan_id,
            channel_name=chan_name,
            current_users=active_usr,
            invited_users=invited_usr,
        )
