
import os as __os


def suite_bin_dirs():
    """Return list of suite bin dir paths

    Returns:
        list: list of path string

    """
    # TODO: deprecate this for local and release suite dirs
    return None


def draft_root():
    """Return draft suite saving dir path"""
    from . import util
    return util.normpath(__os.path.expanduser("~/rez/sweet/drafts"))


def default_root():
    """Return default suite saving dir path"""
    from . import util
    # TODO: put this into root completer, and right click actions
    return util.normpath(__os.path.expanduser("~/rez/sweet/suites"))


def local_suite_dirs():
    # TODO: put this into root completer, and right click actions
    pass


def release_suite_dirs():
    # TODO: put this into root completer, and right click actions
    pass


def suite_save_option_parser(storage):
    """Additional suite data input dialog widget

    The widget must have a signal that emit the input as dict.

    """
    from .vendor import qargparse

    options = [
        qargparse.Integer("arg_hello")
    ]

    parser = qargparse.QArgumentParser(options, storage=storage)

    return parser


def on_suite_saved_callback(suite_dir, options):
    """A callback that runs right after suite is saved

    This could be used to create/update Allzpark profile, or triggering
    VCS.

    Args:
        suite_dir (str): suite saved path
        options (dict)

    Returns:
        None

    """
    return None
