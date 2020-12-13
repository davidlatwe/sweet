

# default suite saving root
default_root = "local"


def saving_roots():
    """Return a dict of suite saving root path
    """
    from collections import OrderedDict as odict
    from . import util
    return odict([
        ("draft", util.normpath("~/rez/sweet/drafts")),
        ("local", util.normpath("~/rez/sweet/suites")),
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
