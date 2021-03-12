
import os
import sys
import logging
from .vendor.Qt5 import QtCore, QtWidgets
from . import control, view, resources

log = logging.getLogger("sweet")
log.setLevel(logging.DEBUG)

_APP_NAME = "Sweet"


def init():
    if sys.platform == "darwin":
        os.environ["QT_MAC_WANTS_LAYER"] = "1"  # MacOS BigSur

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    storage = QtCore.QSettings(QtCore.QSettings.IniFormat,
                               QtCore.QSettings.UserScope,
                               _APP_NAME, "preferences")
    print("Preference file: %s" % storage.fileName())

    resources.load_themes()
    qss = resources.load_theme(name=storage.value("theme"))

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
