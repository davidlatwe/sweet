
import os
import webbrowser
import subprocess


def open_file_location(fname):
    if os.path.exists(fname):
        if os.name == "nt":
            fname = os.path.normpath(fname)
            subprocess.Popen("explorer /select,%s" % fname)
        else:
            webbrowser.open(os.path.dirname(fname))
    else:
        raise OSError("%s did not exist" % fname)


def normpath(path):
    return os.path.normpath(
        os.path.normcase(os.path.abspath(os.path.expanduser(path)))
    ).replace("\\", "/")


def normpaths(*paths):
    return list(map(normpath, paths))
