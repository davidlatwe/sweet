
__version__ = "0.1.1"


def package_info():
    import sweet
    return dict(
        name=sweet.__package__,
        version=__version__,
        path=sweet.__path__[0],
    )


def print_info():
    import sys
    info = package_info()
    py = sys.version_info
    print(info["name"],
          info["version"],
          "from", info["path"],
          "(python {x}.{y})".format(x=py.major, y=py.minor))
