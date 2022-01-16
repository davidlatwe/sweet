
import os


def normpath(path):
    return os.path.normpath(
        os.path.normcase(os.path.abspath(os.path.expanduser(path)))
    ).replace("\\", "/")


def normpaths(*paths):
    return list(map(normpath, paths))
