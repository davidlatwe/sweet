

# default suite saving root
default_root = "local"


def profile_roots():
    from rez.config import config as rez_config
    from collections import OrderedDict as odict

    mongozark = rez_config.plugins.package_repository.mongozark

    return odict([
        ("local", mongozark.rez.install),
        ("release", mongozark.rez.release),
    ])


def suite_roots():
    """Return a dict of suite saving root path
    """
    from collections import OrderedDict as odict
    from . import util
    return odict([
        ("local", util.normpath("~/rez/sweet/local")),
        ("release", util.normpath("~/rez/sweet/release")),
    ])
