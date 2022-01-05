
import os
import functools
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


def attach_sender(sender, func, signal):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        returned = func(*args, **kwargs)
        signal.send(sender)
        return returned
    return wrapper
