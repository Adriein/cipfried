import subprocess
import sys

from cipfried.game import CreatureMovement, FullMap, GameMessage, LoginSuccess, Position, WorldState


def test_creature_movement_is_a_game_message() -> None:
    movement = CreatureMovement(
        opcode=0x6D,
        old_position=Position(1, 2, 3),
        old_stackpos=0,
        new_position=Position(4, 5, 6),
    )

    assert isinstance(movement, GameMessage)
    assert movement.opcode == 0x6D


def test_world_state_tracks_login_and_movement() -> None:
    world = WorldState()
    assert world.player_id is None
    assert world.player_position is None

    world.apply_message(LoginSuccess(opcode=0x0A, player_id=12345))
    assert world.player_id == 12345

    world.apply_message(FullMap(opcode=0x64, player_position=Position(100, 200, 7)))
    assert world.player_position == Position(100, 200, 7)

    # Creature movement that matches player moves the player
    world.apply_message(
        CreatureMovement(
            opcode=0x6D,
            old_position=Position(100, 200, 7),
            old_stackpos=0,
            new_position=Position(101, 200, 7),
        )
    )
    assert world.player_position == Position(101, 200, 7)

    # Creature movement that does not match player does not move player
    world.apply_message(
        CreatureMovement(
            opcode=0x6D,
            old_position=Position(50, 50, 7),
            old_stackpos=0,
            new_position=Position(51, 50, 7),
        )
    )
    assert world.player_position == Position(101, 200, 7)

    world.reset()
    assert world.player_id is None
    assert world.player_position is None


def test_game_package_does_not_import_network() -> None:
    code = "import cipfried.game, sys; assert 'cipfried.network' not in sys.modules"

    subprocess.run([sys.executable, "-c", code], check=True)
