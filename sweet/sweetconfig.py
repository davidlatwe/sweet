

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
