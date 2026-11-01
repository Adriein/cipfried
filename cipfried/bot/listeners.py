import logging

from cipfried.game.messages import CreatureMovement, GameMessage

logger = logging.getLogger(__name__)


def log_creature_movement(message: GameMessage) -> None:
    if not isinstance(message, CreatureMovement):
        return

    logger.info(
        "Creature moved from %s to %s (old stackpos %d)",
        message.old_position,
        message.new_position,
        message.old_stackpos,
    )


__all__ = ["log_creature_movement"]
