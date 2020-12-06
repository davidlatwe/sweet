
from ..vendor.Qt5 import QtCore, QtWidgets


class SuiteView(QtWidgets.QWidget):

    # TODO:
    # draft (template) suite list (right click to import)
    # existing suite list (right click to load/import, search able)
    # batch context re-resolve, match by resolved package (another window ?)

    named = QtCore.Signal(str)
    dired = QtCore.Signal(str)
    commented = QtCore.Signal(str)
    saved = QtCore.Signal()
    drafted = QtCore.Signal()

    def __init__(self, parent=None):
        super(SuiteView, self).__init__(parent=parent)
        self.setObjectName("SuiteView")

        widgets = {
            "name": QtWidgets.QLineEdit(),  # TODO: add name validator
            "dir": QtWidgets.QLineEdit(),
            "desc": QtWidgets.QTextEdit(),
            "save": QtWidgets.QPushButton("Save Suite"),
            "draft": QtWidgets.QPushButton("Save Draft"),
        }

        widgets["name"].setPlaceholderText("Suite name..")
        widgets["dir"].setPlaceholderText("Suite dir..")
        widgets["desc"].setPlaceholderText("Suite description.. (optional)")
        widgets["desc"].setAcceptRichText(False)
        widgets["desc"].setTabChangesFocus(True)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(2, 8, 2, 2)
        layout.addWidget(widgets["name"])
        layout.addWidget(widgets["dir"])
        layout.addWidget(widgets["desc"])
        layout.addWidget(widgets["save"])
        layout.addWidget(widgets["draft"])
        layout.setAlignment(QtCore.Qt.AlignTop)

        widgets["name"].textChanged.connect(self.named.emit)
        widgets["dir"].textChanged.connect(self.dired.emit)
        widgets["desc"].textChanged.connect(self.on_description_changed)
        widgets["save"].clicked.connect(self.saved.emit)
        widgets["draft"].clicked.connect(self.drafted.emit)

        self._widgets = widgets

    def on_description_changed(self):
        text = self._widgets["desc"].toPlainText()
        self.commented.emit(text)
