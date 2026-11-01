from enum import IntEnum


class ServerOpcode(IntEnum):
    """Server-to-client opcodes used by the analysis layer.

    Add entries here as you identify them. The value below is the movement
    opcode you already worked out; change it if your capture uses another one.
    """

    CREATURE_MOVE = 0x6D


__all__ = ["ServerOpcode"]
