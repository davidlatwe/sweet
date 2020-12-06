
from ..vendor.Qt5 import QtCore, QtWidgets


class SuiteView(QtWidgets.QWidget):

    # TODO:
    # draft (template) suite list (right click to import)
    # existing suite list (right click to load/import, search able)
    # batch context re-resolve, match by resolved package (another window ?)

    suite_named = QtCore.Signal(str)
    suite_dired = QtCore.Signal(str)
    suite_saved = QtCore.Signal()

    def __init__(self, parent=None):
        super(SuiteView, self).__init__(parent=parent)
        self.setObjectName("SuiteView")

        widgets = {
            "name": QtWidgets.QLineEdit(),  # TODO: add name validator
            "dir": QtWidgets.QLineEdit(),
            "save": QtWidgets.QPushButton("Save Suite"),
            "draft": QtWidgets.QPushButton("Save Draft"),
        }

        widgets["name"].setPlaceholderText("Suite name..")
        widgets["dir"].setPlaceholderText("Suite dir..")

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(widgets["name"])
        layout.addWidget(widgets["dir"])
        layout.addWidget(widgets["save"])
        layout.addWidget(widgets["draft"])
        layout.setAlignment(QtCore.Qt.AlignTop)

        widgets["name"].textChanged.connect(self.suite_named.emit)
        widgets["dir"].textChanged.connect(self.suite_dired.emit)
        widgets["save"].clicked.connect(self.suite_saved.emit)
