
import os as __os


def suites():
    """Return list of suite path

    Returns:
        list: list of path string

    """
    from rez.suite import Suite
    return Suite.visible_suite_paths()


def draft_root():
    """Return draft suite saving dir path"""
    return __os.path.expanduser("~/sweet/drafts")
