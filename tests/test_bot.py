import logging

from cipfried.bot import log_creature_movement
from cipfried.game import CreatureMovement, GameMessage, Position


def test_log_creature_movement_logs_movement(caplog) -> None:
    movement = CreatureMovement(
        opcode=0x6D,
        old_position=Position(1, 2, 3),
        old_stackpos=0,
        new_position=Position(4, 5, 6),
    )

    with caplog.at_level(logging.INFO):
        log_creature_movement(movement)

    assert "Creature moved" in caplog.text
    assert "Position(x=1, y=2, z=3)" in caplog.text
    assert "Position(x=4, y=5, z=6)" in caplog.text


def test_log_creature_movement_ignores_other_messages(caplog) -> None:
    with caplog.at_level(logging.INFO):
        log_creature_movement(GameMessage(opcode=0x01))

    assert caplog.text == ""
