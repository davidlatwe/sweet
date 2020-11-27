
from rez.packages_ import iter_package_families, iter_packages


def scan():
    results = list()

    for family in iter_package_families():
        name = family.name
        path = family.resource.location

        for package in iter_packages(name, paths=[path]):
            qualified_name = package.qualified_name
            version = str(package.version)
            tools = package.tools or []
            uri = package.uri

            doc = {
                "family": name,
                "version": version,
                "uri": uri,
                "tools": tools,
                "qualified_name": qualified_name,
            }
            results.append(doc)

    return results
