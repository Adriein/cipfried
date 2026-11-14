from __future__ import annotations

import subprocess
import sys

from cipfried.game.creature import Creature
from cipfried.game.item import Item
from cipfried.game.messages import CreatureMovement, FullMap, GameMessage, LoginSuccess
from cipfried.game.position import Position
from cipfried.game.tile import Tile, tile_position_from_index
from cipfried.game.world import WorldState


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


def test_tile_position_from_index() -> None:
    player = Position(x=32253, y=32063, z=7)

    # Upper-left corner: index 0
    pos_0 = tile_position_from_index(player, 0)
    assert pos_0 == Position(x=32245, y=32057, z=7)

    # 1 square down the first column: index 1
    pos_1 = tile_position_from_index(player, 1)
    assert pos_1 == Position(x=32245, y=32058, z=7)

    # Bottom of first column (14th square): index 13
    pos_13 = tile_position_from_index(player, 13)
    assert pos_13 == Position(x=32245, y=32070, z=7)

    # Top of second column: index 14
    pos_14 = tile_position_from_index(player, 14)
    assert pos_14 == Position(x=32246, y=32057, z=7)

    # Player position in the middle: col 8, row 6 -> 8 * 14 + 6 = 118
    pos_center = tile_position_from_index(player, 118)
    assert pos_center == player

    # Bottom-right corner: 18 * 14 - 1 = 251
    pos_last = tile_position_from_index(player, 251)
    assert pos_last == Position(x=32262, y=32070, z=7)


def test_item_and_creature_tile_structure() -> None:
    item = Item(id=3031, qty=100)
    assert item.id == 3031
    assert item.qty == 100

    creature = Creature(
        id=0x40000001,
        name="Rat",
        creature_type=0,
        health_percentage=100,
        facing_dir=2,
        speed=110,
    )
    assert creature.name == "Rat"

    tile = Tile(position=Position(100, 100, 7), ground_id=103)
    tile.add_item(item)
    tile.add_creature(creature)

    assert tile.ground_id == 103
    assert tile.items == [item]
    assert tile.creatures == [creature]
    assert creature.position == tile.position

    tile.remove_creature(creature)
    assert tile.creatures == []


def test_world_state_tiles_storage() -> None:
    world = WorldState()
    pos = Position(32000, 32000, 7)
    tile = Tile(position=pos, ground_id=100)

    world.set_tile(tile)
    assert world.get_tile(pos) == tile
    assert world.tiles[pos] == tile

    world.reset()
    assert world.get_tile(pos) is None
    assert world.tiles == {}


def test_world_state_full_map_populates_tiles_and_creatures() -> None:
    world = WorldState()
    p_pos = Position(32000, 32000, 7)
    c_pos = Position(32001, 32000, 7)

    creature = Creature(id=0x40000001, name="Rat", position=c_pos)
    tile1 = Tile(position=p_pos, ground_id=100)
    tile2 = Tile(position=c_pos, ground_id=101)
    tile2.add_creature(creature)

    msg = FullMap(opcode=0x64, player_position=p_pos, tiles=(tile1, tile2))
    world.apply_message(msg)

    assert world.player_position == p_pos
    assert world.get_tile(p_pos) == tile1
    assert world.get_tile(c_pos) == tile2
    assert world.get_creature(0x40000001) == creature


def test_world_state_creature_movement_updates_tiles_and_creatures() -> None:
    world = WorldState()
    old_pos = Position(32000, 32000, 7)
    new_pos = Position(32001, 32000, 7)

    creature = Creature(id=0x40000001, name="Rat", position=old_pos)
    old_tile = Tile(position=old_pos, ground_id=100)
    old_tile.add_creature(creature)
    new_tile = Tile(position=new_pos, ground_id=100)

    world.set_tile(old_tile)
    world.set_tile(new_tile)
    assert creature in world.get_tile(old_pos).creatures

    # Move creature from old_pos to new_pos
    movement = CreatureMovement(
        opcode=0x6D,
        old_position=old_pos,
        old_stackpos=0,
        new_position=new_pos,
    )
    world.apply_message(movement)

    # Creature should be removed from old tile
    assert creature not in world.get_tile(old_pos).creatures
    # Creature should be on new tile with updated position
    assert creature in world.get_tile(new_pos).creatures
    assert creature.position == new_pos
    assert world.get_creature(0x40000001).position == new_pos


def test_world_state_creature_movement_missing_tile_does_not_crash() -> None:
    world = WorldState()
    old_pos = Position(32000, 32000, 7)
    new_pos = Position(32001, 32000, 7)

    movement = CreatureMovement(
        opcode=0x6D,
        old_position=old_pos,
        old_stackpos=0,
        new_position=new_pos,
    )
    # Should not raise an exception even if tiles are not yet in state
    world.apply_message(movement)
    assert world.get_tile(old_pos) is None
    assert world.get_tile(new_pos) is None


def test_game_package_does_not_import_network() -> None:
    code = "import cipfried.game, sys; assert 'cipfried.network' not in sys.modules"

    subprocess.run([sys.executable, "-c", code], check=True)
