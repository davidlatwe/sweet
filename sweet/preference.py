
from .vendor.Qt5 import QtCore, QtWidgets
from .vendor import qargparse


class Preference(QtWidgets.QWidget):
    changed = QtCore.Signal(str, object)

    def __init__(self, ctrl, parent=None):
        super(Preference, self).__init__(parent=parent)

        options = [
            qargparse.Integer("recentSuiteCount", default=10),
            qargparse.Enum("suiteOpenAs", items=["Ask", "Loaded", "Import"]),
        ]

        widgets = {
            "scroll": QtWidgets.QScrollArea(),
            "options": qargparse.QArgumentParser(options)
        }

        widgets["scroll"].setWidget(widgets["options"])
        widgets["scroll"].setWidgetResizable(True)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(widgets["scroll"])

        widgets["options"].changed.connect(self.on_option_changed)

        self._widgets = widgets
        self._ctrl = ctrl

    def retrieve(self):
        pass

    def on_option_changed(self, argument):
        name = argument["name"]
        value = argument.read()
        self._ctrl.store(name, value)
        self.changed.emit(name, value)
