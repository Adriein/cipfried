from __future__ import annotations

import logging

from cipfried.bot.fsm import StateMachine
from cipfried.bot.listeners import log_creature_movement
from cipfried.bot.walker import IdleState, Pathfinder, WalkingState
from cipfried.bot.worker import BotWorker
from cipfried.core.context import Context, State
from cipfried.game.messages import CreatureMovement, GameMessage
from cipfried.game.position import Position


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


def test_bot_worker_synchronous_stepping() -> None:
    ctx = Context(game_state=State())
    ticks: list[tuple[Context, float]] = []

    def on_tick(context: Context, now: float) -> None:
        ticks.append((context, now))

    worker = BotWorker(context=ctx, on_tick=on_tick)
    assert worker.tick_count == 0
    assert not worker.is_running

    worker.step(now=100.0)
    assert worker.tick_count == 1
    assert worker.last_tick_time == 100.0
    assert len(ticks) == 1
    assert ticks[0] == (ctx, 100.0)

    worker.step(now=100.05)
    assert worker.tick_count == 2
    assert worker.last_tick_time == 100.05
    assert len(ticks) == 2


def test_bot_worker_background_thread_lifecycle() -> None:
    import time

    ctx = Context(game_state=State())
    worker = BotWorker(context=ctx, interval=0.01)

    assert not worker.is_running
    worker.start()
    assert worker.is_running

    # Let it tick for a brief period
    time.sleep(0.05)
    assert worker.tick_count >= 2

    worker.stop()
    assert not worker.is_running


def test_bot_worker_handles_handler_exceptions(caplog) -> None:
    ctx = Context(game_state=State())

    def failing_handler(context: Context, now: float) -> None:
        raise RuntimeError("boom")

    worker = BotWorker(context=ctx, on_tick=failing_handler)
    # Should not raise
    worker.step()
    assert worker.tick_count == 1


def test_bot_worker_state_machine_walk_vs_heal() -> None:
    """Demonstrates state machine handling action exclusivity (walk vs heal)."""
    from enum import Enum

    class ActionState(Enum):
        IDLE = "idle"
        WALKING = "walking"
        HEALING = "healing"

    class SimpleBot:
        def __init__(self) -> None:
            self.state = ActionState.IDLE
            self.hp_percent = 100
            self.step_finish_time = 0.0
            self.actions_taken: list[str] = []

        def on_tick(self, ctx: Context, now: float) -> None:
            # 1. Emergency priority: HP low -> interrupt/emergency heal
            if self.hp_percent < 40:
                self.state = ActionState.HEALING
                self.actions_taken.append(f"heal at {now}")
                return

            # 2. Walking: cannot heal/act until step duration finishes
            if self.state == ActionState.WALKING:
                if now < self.step_finish_time:
                    # Still walking, wait for animation
                    return
                # Step finished
                self.state = ActionState.IDLE
                self.actions_taken.append(f"step finished at {now}")

    bot = SimpleBot()
    ctx = Context(game_state=State())
    worker = BotWorker(context=ctx, on_tick=bot.on_tick)

    # Start walking at t=10.0, step finishes at t=10.2
    bot.state = ActionState.WALKING
    bot.step_finish_time = 10.2

    # Tick at t=10.1: still walking, no actions
    worker.step(now=10.1)
    assert bot.state == ActionState.WALKING
    assert len(bot.actions_taken) == 0

    # Tick at t=10.15: emergency damage arrives! (HP drops to 30%)
    bot.hp_percent = 30
    worker.step(now=10.15)
    assert bot.state == ActionState.HEALING
    assert bot.actions_taken == ["heal at 10.15"]


def test_fsm_walker_integration_with_bot_worker(capsys) -> None:
    ctx = Context(game_state=State())
    ctx.world.player_position = Position(32000, 32000, 7)

    fsm = StateMachine(initial_state=IdleState())
    worker = BotWorker(context=ctx, on_tick=fsm.tick)

    # Tick 1: Idle state executes
    worker.step(now=1.0)
    assert isinstance(fsm.current_state, IdleState)

    # Transition to WalkingState
    goal = Position(32005, 32000, 7)
    fsm.change_state(WalkingState(destination=goal), ctx)
    assert isinstance(fsm.current_state, WalkingState)
    assert fsm.current_state.path == [goal]

    # Tick 2: Walking state executes
    worker.step(now=1.05)

    captured = capsys.readouterr().out
    assert "[IdleState] Entered Idle state." in captured
    assert "[WalkingState] Started walking towards Position(x=32005, y=32000, z=7)." in captured
    assert "[WalkingState] Tick at 1.05. Steps remaining: 1." in captured
