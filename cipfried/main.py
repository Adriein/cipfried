import logging
import os

from cipfried.core.engine import Engine

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
LOG_LEVEL = os.environ.get("CIPFRIED_LOG_LEVEL", "INFO").upper()


def configure_logging() -> None:
    logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO), format=LOG_FORMAT)


def main() -> None:
    configure_logging()

    engine = Engine()
    engine.start()


if __name__ == "__main__":
    main()
