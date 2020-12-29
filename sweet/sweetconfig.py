

# default suite saving root
default_root = "local"


def suite_roots():
    """Return a dict of suite saving root path
    """
    from collections import OrderedDict as odict
    from . import util
    return odict([
        ("local", util.normpath("~/rez/sweet/local")),
        ("release", util.normpath("~/rez/sweet/release")),
    ])


def on_suite_saved_callback(suite_dir):
    """A callback that runs after suite saved

    Args:
        suite_dir (str): suite saved path

    Returns:
        None

    """
    return None
