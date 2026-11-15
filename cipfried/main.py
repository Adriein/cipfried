from __future__ import annotations

import logging
import logging.handlers
import os
import pathlib

from cipfried.analysis.parsers.creature_move import CreatureMoveParser
from cipfried.analysis.parsers.full_map import FullMapParser
from cipfried.analysis.parsers.login_success import LoginSuccessParser
from cipfried.analysis.parsers.open_channel import OpenChannelParser
from cipfried.analysis.parsers.world_entered import WorldEnteredParser
from cipfried.analysis.pipeline import MessagePipeline
from cipfried.bot.fsm import StateMachine
from cipfried.bot.walker import IdleState
from cipfried.bot.worker import BotWorker
from cipfried.core.engine import Engine

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
LOG_LEVEL = os.environ.get("CIPFRIED_LOG_LEVEL", "INFO").upper()

# Per-module overrides:
#   CIPFRIED_LOG_LEVEL_NETWORK=WARNING  -> silences cipfried.network.*
#   CIPFRIED_LOG_LEVEL_STREAM=WARNING   -> silences cipfried.network.stream only
#   CIPFRIED_LOG_LEVEL_SNIFFER=WARNING  -> silences cipfried.network.sniffer only
#   CIPFRIED_LOG_LEVEL_ANALYSIS=DEBUG   -> verbose parser output
_MODULE_ENV_OVERRIDES: dict[str, str] = {
    "cipfried.network":         "CIPFRIED_LOG_LEVEL_NETWORK",
    "cipfried.network.stream":  "CIPFRIED_LOG_LEVEL_STREAM",
    "cipfried.network.sniffer": "CIPFRIED_LOG_LEVEL_SNIFFER",
    "cipfried.analysis":        "CIPFRIED_LOG_LEVEL_ANALYSIS",
    "cipfried.bot":             "CIPFRIED_LOG_LEVEL_BOT",
    "cipfried.core":            "CIPFRIED_LOG_LEVEL_CORE",
}

# Session packet capture:
#   CIPFRIED_SESSION_FILE=debug/session.txt  -> write raw server packets to file
#   Leave unset to disable file capture entirely.
SESSION_FILE = os.environ.get("CIPFRIED_SESSION_FILE", "")


def configure_logging() -> None:
    root_level = getattr(logging, LOG_LEVEL, logging.INFO)
    logging.basicConfig(level=root_level, format=LOG_FORMAT)

    # Apply per-module level overrides from env vars
    for logger_name, env_var in _MODULE_ENV_OVERRIDES.items():
        raw = os.environ.get(env_var, "").upper()
        if raw:
            level = getattr(logging, raw, None)
            if level is not None:
                logging.getLogger(logger_name).setLevel(level)
            else:
                logging.warning("Unknown log level %r in %s; ignoring.", raw, env_var)


def configure_session_logger(path: str) -> logging.Logger:
    """Set up a dedicated file logger for raw session packet capture.

    Each line written is:
        cmd: 0xXX, payload: aa bb cc ...
    """
    dest = pathlib.Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)

    session_logger = logging.getLogger("cipfried.session")
    session_logger.setLevel(logging.DEBUG)
    session_logger.propagate = False  # don't echo to console

    handler = logging.FileHandler(dest, mode="a", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(message)s"))
    session_logger.addHandler(handler)

    logging.getLogger(__name__).info("Session capture writing to: %s", dest)
    return session_logger


def main() -> None:
    configure_logging()

    session_logger: logging.Logger | None = None
    if SESSION_FILE:
        session_logger = configure_session_logger(SESSION_FILE)

    pipeline = MessagePipeline()
    pipeline.register(CreatureMoveParser())
    pipeline.register(FullMapParser())
    pipeline.register(LoginSuccessParser())
    pipeline.register(OpenChannelParser())
    pipeline.register(WorldEnteredParser())

    engine = Engine(message_pipeline=pipeline, session_logger=session_logger)
    pipeline.add_listener(engine.context.world.apply_message)

    fsm = StateMachine(initial_state=IdleState())
    engine.bot_worker = BotWorker(context=engine.context, interval=50, on_tick=fsm.tick)

    engine.start()


if __name__ == "__main__":
    main()
