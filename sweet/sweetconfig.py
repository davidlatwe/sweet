
import os as __os


def suite_bin_dirs():
    """Return list of suite bin dir paths

    Returns:
        list: list of path string

    """
    return None


def draft_root():
    """Return draft suite saving dir path"""
    from . import util
    return util.normpath(__os.path.expanduser("~/rez/sweet/drafts"))


def default_root():
    """Return default suite saving dir path"""
    from . import util
    return util.normpath(__os.path.expanduser("~/rez/sweet/suites"))
