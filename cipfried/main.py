import logging
import os

from cipfried.analysis import MessagePipeline
from cipfried.analysis.parsers import CreatureMoveParser
from cipfried.bot import log_creature_movement
from cipfried.core.engine import Engine

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
LOG_LEVEL = os.environ.get("CIPFRIED_LOG_LEVEL", "INFO").upper()


def configure_logging() -> None:
    logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO), format=LOG_FORMAT)


def main() -> None:
    configure_logging()

    pipeline = MessagePipeline()
    pipeline.register(CreatureMoveParser())
    pipeline.add_listener(log_creature_movement)
    engine = Engine(message_pipeline=pipeline)
    engine.start()


if __name__ == "__main__":
    main()
