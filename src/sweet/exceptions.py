
import sys
import warnings
from rez.exceptions import RezError, SuiteError

__all__ = (
    "RezError",
    "SuiteError",
    "SweetError",
    "SuiteOpError",
    "SuiteIOError",

    "SweetWarning",
    "SuiteOpWarning",
    "ContextNameWarning",
    "ContextBrokenWarning",
)


# errors

class SweetError(Exception):
    """Sweet base error"""


class SuiteOpError(SweetError):
    """Suite operation error"""


class SuiteIOError(SweetError):
    """Suite save/load related error"""


# warnings

class SweetWarning(UserWarning):
    """Sweet base warning"""


if not sys.warnoptions:
    warnings.filterwarnings("error", category=SweetWarning)


class SuiteOpWarning(SweetWarning):
    """Suite operation warning"""


class ContextNameWarning(SweetWarning):
    """Suite context naming warning"""


class ContextBrokenWarning(SweetWarning):
    """Suite context resolve failed warning"""
