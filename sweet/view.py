
from Qt5 import QtCore, QtGui, QtWidgets

from .version import version
from .search.view import PackageView
from .sphere.view import SphereView
from . import resources as res


class Window(QtWidgets.QMainWindow):
    title = "Sweet %s" % version

    def __init__(self, ctrl, parent=None):
        super(Window, self).__init__(parent)
        self.setWindowTitle(self.title)
        self.setAttribute(QtCore.Qt.WA_StyledBackground)
        # self.setWindowIcon(QtGui.QIcon(res.find("Logo_64.png")))

        panels = {
            "body": QtWidgets.QWidget(),
        }

        widgets = {
            "package": PackageView(),
            "sphere": SphereView(),
        }

        widgets["package"].set_model(ctrl.models["package"])
        widgets["sphere"].set_completer_model(ctrl.models["package"])

        layout = QtWidgets.QHBoxLayout(panels["body"])
        layout.addWidget(widgets["package"])
        layout.addWidget(widgets["sphere"])

        self._ctrl = ctrl
        self._panels = panels
        self._widgets = widgets

        self.setCentralWidget(panels["body"])
        self.setFocus()
