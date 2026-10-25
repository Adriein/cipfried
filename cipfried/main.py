import logging

from cipfried.core.engine import Engine

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)


def main() -> None:
    configure_logging()

    engine = Engine()
    engine.start()


if __name__ == "__main__":
    main()
