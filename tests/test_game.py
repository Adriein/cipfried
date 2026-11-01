import subprocess
import sys

from cipfried.game import CreatureMovement, GameMessage, Position


def test_creature_movement_is_a_game_message() -> None:
    movement = CreatureMovement(
        opcode=0x6D,
        old_position=Position(1, 2, 3),
        old_stackpos=0,
        new_position=Position(4, 5, 6),
    )

    assert isinstance(movement, GameMessage)
    assert movement.opcode == 0x6D


def test_game_package_does_not_import_network() -> None:
    code = "import cipfried.game, sys; assert 'cipfried.network' not in sys.modules"

    subprocess.run([sys.executable, "-c", code], check=True)
