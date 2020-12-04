
from Qt5 import QtWidgets
from . import control, view, resources


def main():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    resources.load_themes()
    qss = resources.load_theme()

    ctrl = control.Controller()
    window = view.Window(ctrl=ctrl)
    window.setStyleSheet(qss)
    window.show()

    ctrl.search_packages(on_time=200)
    app.exec_()
