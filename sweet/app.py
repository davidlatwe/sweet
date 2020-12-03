
import sys
from Qt5 import QtWidgets
from .search.model import PackageModel
from .search.view import PackageView
from .sphere.view import SphereView
from . import resources, lib

self = sys.modules[__name__]
self.window = None


class App(QtWidgets.QWidget):

    def __init__(self, parent=None):
        super(App, self).__init__(parent=parent)

        widgets = {
            "search": PackageView(),
            "sphere": SphereView(),
        }

        model = PackageModel()
        widgets["search"].setModel(model)
        widgets["sphere"].set_completer_model(model)

        layout = QtWidgets.QHBoxLayout(self)
        layout.addWidget(widgets["search"])
        layout.addWidget(widgets["sphere"])

        self._widgets = widgets

    def reset(self):
        self._widgets["search"].reset(lib.scan())


def show():
    resources.load_themes()
    qss = resources.load_theme()
    app = App()
    app.setStyleSheet(qss)
    app.show()
    app.reset()

    self.window = app
