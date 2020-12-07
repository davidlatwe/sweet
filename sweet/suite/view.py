
import os
from ..vendor.Qt5 import QtCore, QtGui, QtWidgets
from ..common.view import SlimTableView
from .model import SuiteDraftModel


class SuiteView(QtWidgets.QWidget):

    # TODO:
    # existing suite list (right click to load/import, search able)
    # batch context re-resolve, match by resolved package (another window ?)

    named = QtCore.Signal(str)
    dired = QtCore.Signal(str)
    commented = QtCore.Signal(str)
    saved = QtCore.Signal()
    loaded = QtCore.Signal(str)

    def __init__(self, parent=None):
        super(SuiteView, self).__init__(parent=parent)
        self.setObjectName("SuiteView")

        widgets = {
            "name": QtWidgets.QLineEdit(),  # TODO: add name validator
            "dir": QtWidgets.QLineEdit(),
            "desc": QtWidgets.QTextEdit(),
            "save": QtWidgets.QPushButton("Save Suite"),
            "draftView": QtWidgets.QWidget(),
            "draftList": SlimTableView(),
            "draftDesc": QtWidgets.QTextEdit(),
        }

        widgets["name"].setPlaceholderText("Suite name..")
        widgets["dir"].setPlaceholderText("Suite dir..")
        widgets["desc"].setPlaceholderText("Suite description.. (optional)")
        widgets["desc"].setAcceptRichText(False)
        widgets["desc"].setTabChangesFocus(True)
        widgets["draftDesc"].setReadOnly(True)
        widgets["draftList"].setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        widgets["draftList"].customContextMenuRequested.connect(
            self.on_draft_right_clicked)

        layout = QtWidgets.QHBoxLayout(widgets["draftView"])
        layout.addWidget(widgets["draftList"])
        layout.addWidget(widgets["draftDesc"])

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(2, 8, 2, 2)
        layout.addWidget(widgets["name"])
        layout.addWidget(widgets["dir"])
        layout.addWidget(widgets["desc"])
        layout.addWidget(widgets["save"])
        layout.addWidget(widgets["draftView"])
        layout.setAlignment(QtCore.Qt.AlignTop)

        widgets["name"].textChanged.connect(self.named.emit)
        widgets["dir"].textChanged.connect(self.dired.emit)
        widgets["desc"].textChanged.connect(self.on_description_changed)
        widgets["save"].clicked.connect(self.saved.emit)

        self._widgets = widgets

    def on_description_changed(self):
        text = self._widgets["desc"].toPlainText()
        self.commented.emit(text)

    def on_draft_selection_changed(self, selected, deselected):
        selected = selected.indexes()
        text = ""
        if selected:
            text = selected[0].data(role=SuiteDraftModel.DescriptionRole)
        self._widgets["draftDesc"].setText(text)

    def on_draft_right_clicked(self, position):
        index = self._widgets["draftList"].indexAt(position)

        if not index.isValid():
            # Clicked outside any item
            return

        menu = QtWidgets.QMenu(self)
        load = QtWidgets.QAction("Load", menu)

        menu.addAction(load)

        def on_load():
            data = index.data(role=SuiteDraftModel.ItemRole)
            self.loaded.emit(data["path"])

            self._widgets["dir"].setText(data["root"])
            self._widgets["name"].setText(data["name"])
            self._widgets["desc"].setText(data["description"])

        load.triggered.connect(on_load)

        menu.move(QtGui.QCursor.pos())
        menu.show()

    def set_model(self, draft):
        self._widgets["draftList"].setModel(draft)
        sel_model = self._widgets["draftList"].selectionModel()
        sel_model.selectionChanged.connect(self.on_draft_selection_changed)
