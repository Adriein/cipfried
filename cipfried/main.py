from __future__ import annotations

import logging
import os

from cipfried.analysis.parsers.creature_move import CreatureMoveParser
from cipfried.analysis.parsers.login_success import LoginSuccessParser
from cipfried.analysis.parsers.open_channel import OpenChannelParser
from cipfried.analysis.parsers.world_entered import WorldEnteredParser
from cipfried.analysis.pipeline import MessagePipeline
from cipfried.bot.listeners import log_creature_movement
from cipfried.core.engine import Engine

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
LOG_LEVEL = os.environ.get("CIPFRIED_LOG_LEVEL", "INFO").upper()


def configure_logging() -> None:
    logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO), format=LOG_FORMAT)


def main() -> None:
    configure_logging()

    pipeline = MessagePipeline()
    pipeline.register(CreatureMoveParser())
    pipeline.register(LoginSuccessParser())
    pipeline.register(OpenChannelParser())
    pipeline.register(WorldEnteredParser())
    pipeline.add_listener(log_creature_movement)

    engine = Engine(message_pipeline=pipeline)
    pipeline.add_listener(engine.context.world.apply_message)
    engine.start()


if __name__ == "__main__":
    main()
