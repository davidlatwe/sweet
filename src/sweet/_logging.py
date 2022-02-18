
import logging
from colorama import init, Fore

init(autoreset=True)


class ColorFormatter(logging.Formatter):
    Colors = {
        "DEBUG": Fore.BLUE,
        "INFO": Fore.GREEN,
        "WARNING": Fore.YELLOW,
        "ERROR": Fore.RED,
        "CRITICAL": Fore.MAGENTA,
    }

    def format(self, record):
        color = self.Colors.get(record.levelname, "")
        return color + logging.Formatter.format(self, record)


def init_logging():
    formatter = ColorFormatter(
        fmt="%(asctime)s %(levelname)-8s %(message)s",
        datefmt="%X"
    )

    handler = logging.StreamHandler()
    handler.set_name("stream")
    handler.setFormatter(formatter)
    handler.setLevel(logging.WARNING)

    logger = logging.getLogger("sweet")
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)


init_logging()
