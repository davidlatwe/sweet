
import os
import sys
from Qt5 import QtWidgets
from .view import PackageView
from .model import PackageModel
from .. import lib, resources


def show():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    resources.load_themes()
    qss = resources.load_theme()

    view = PackageView()
    model = PackageModel()

    view.setStyleSheet(qss)

    view.setModel(model)
    view.reset(lib.scan())
    view.show()
    return app.exec_()


os.environ["QT_MAC_WANTS_LAYER"] = "1"  # MacOS BigSur
sys.exit(show())
