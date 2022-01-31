
import logging


def init_logging():
    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)-8s %(message)s",
        datefmt="%X"
    )

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    logger = logging.getLogger("sweet")
    logger.addHandler(handler)
    logger.setLevel(logging.WARNING)


init_logging()
