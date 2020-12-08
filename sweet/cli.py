
import os
import sys
from .vendor.Qt5 import QtCore, QtWidgets
from . import control, view, resources, sweetconfig


UserError = type("UserError", (Exception,), {})


def _load_userconfig(fname=None):
    fname = fname or os.getenv(
        "SWEET_CONFIG_FILE",
        os.path.expanduser("~/sweetconfig.py")
    )

    mod = {
        "__file__": fname,
    }

    try:
        with open(fname) as f:
            exec(compile(f.read(), f.name, "exec"), mod)

    except IOError:
        raise

    except Exception:
        raise UserError("Better double-check your sweet user config")

    for key in dir(sweetconfig):
        if key.startswith("__"):
            continue

        try:
            value = mod[key]
        except KeyError:
            continue

        setattr(sweetconfig, key, value)

    return fname


def init():
    if sys.platform == "darwin":
        os.environ["QT_MAC_WANTS_LAYER"] = "1"  # MacOS BigSur

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    storage = QtCore.QSettings(QtCore.QSettings.IniFormat,
                               QtCore.QSettings.UserScope,
                               "Sweet", "preferences")
    print("Preference file: %s" % storage.fileName())

    try:
        _load_userconfig()
    except IOError:
        pass

    resources.load_themes()
    qss = resources.load_theme()

    ctrl = control.Controller(storage)
    window = view.Window(ctrl=ctrl)
    window.setStyleSheet(qss)

    return app, window, ctrl


def main():
    app, window, ctrl = init()
    window.show()

    ctrl.defer_search_packages(on_time=200)
    ctrl.defer_list_saved_suites(on_time=200)

    return app.exec_()
