

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


# suite save options .ini file name
save_options_ini = "defaultSuiteOptions"


def suite_save_options():
    """Additional suite save option widgets

    Returns:
        list: A list of qargparse.QArgument instance

    """
    from .vendor import qargparse
    return []


def on_suite_saved_callback(suite_dir, options):
    """A callback that runs after suite saved

    This could be used to create/update Allzpark profile, or triggering
    VCS.

    Args:
        suite_dir (str): suite saved path
        options (dict): suite save options

    Returns:
        None

    """
    return None


def profile_roots():
    from rez.config import config as rez_config
    from collections import OrderedDict as odict

    mongozark = rez_config.plugins.package_repository.mongozark

    return odict([
        ("local", mongozark.rez.install),
        ("release", mongozark.rez.release),
    ])
