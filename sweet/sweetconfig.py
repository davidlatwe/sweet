
import os as __os


def suites():
    """Return list of suite name and path

    Returns:
        list: list of tuple (name, path)

    """
    from rez.suite import Suite

    result = list()
    for path in Suite.visible_suite_paths():
        name = __os.path.basename(path)
        result.append((name, path))

    return result
