
from rez.config import config as rez_config
from rez.packages import iter_package_families


def profiles():
    """Return list of profiles

    This function is called asynchronously, and is suitable
    for making complex filesystem or database queries.
    Can also be a variable of type tuple or list

    """
    profile_paths = [path for path in rez_config.packages_path
                     if path.startswith("mongozark@")]

    _profiles = list()
    for pkg_family in iter_package_families(paths=profile_paths):
        _profiles.append(pkg_family.name)

    return _profiles
