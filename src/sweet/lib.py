
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


def attach_sender(sender, func, signal):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        returned = func(*args, **kwargs)
        signal.send(sender)
        return returned
    return wrapper


class Singleton(type):
    """A metaclass for creating singleton
    https://stackoverflow.com/q/6760685/14054728
    """
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]
