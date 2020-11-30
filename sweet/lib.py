
from rez.packages_ import iter_package_families, iter_packages
from rez.config import config


def scan(no_local=False):
    paths = None
    seen = dict()

    if no_local:
        paths = config.nonlocal_packages_path

    for family in iter_package_families(paths=paths):
        name = family.name
        path = family.resource.location

        for package in iter_packages(name, paths=[path]):
            qualified_name = package.qualified_name

            if qualified_name in seen:
                seen[qualified_name]["locations"].append(path)
                continue

            doc = {
                "family": name,
                "version": str(package.version),
                "uri": package.uri,
                "tools": package.tools or [],
                "qualified_name": qualified_name,
                "timestamp": package.timestamp,
                "locations": [path],
            }
            seen[qualified_name] = doc

            yield doc
