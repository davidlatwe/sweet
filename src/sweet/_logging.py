
import logging


def init_logging():
    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)-8s %(message)s",
        datefmt="%X"
    )

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    handler.setLevel(logging.WARNING)

    logger = logging.getLogger("sweet")
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)


init_logging()
