
import os
import sys
from .vendor.Qt5 import QtCore, QtWidgets
from . import control, view, resources


def main():
    if sys.platform == "darwin":
        os.environ["QT_MAC_WANTS_LAYER"] = "1"  # MacOS BigSur

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    storage = QtCore.QSettings(QtCore.QSettings.IniFormat,
                               QtCore.QSettings.UserScope,
                               "Sweet", "preferences")
    print("Preference file: %s" % storage.fileName())

    resources.load_themes()
    qss = resources.load_theme()

    ctrl = control.Controller(storage)
    window = view.Window(ctrl=ctrl)
    window.setStyleSheet(qss)
    window.show()

    ctrl.defer_search_packages(on_time=200)
    return app.exec_()
