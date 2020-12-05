
import os
import sys
from Qt5 import QtWidgets
from . import control, view, resources


def main():
    if sys.platform == "darwin":
        os.environ["QT_MAC_WANTS_LAYER"] = "1"  # MacOS BigSur

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    resources.load_themes()
    qss = resources.load_theme()

    ctrl = control.Controller()
    window = view.Window(ctrl=ctrl)
    window.setStyleSheet(qss)
    window.show()

    ctrl.defer_search_packages(on_time=200)
    return app.exec_()
