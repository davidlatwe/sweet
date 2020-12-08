
from ..vendor.Qt5 import QtCore, QtGui, QtWidgets
from ..common.view import SlimTableView
from .model import SavedSuiteModel
from .. import util


class SuiteView(QtWidgets.QWidget):

    # TODO:
    #   batch context re-resolve, match by resolved package (another window ?)

    named = QtCore.Signal(str)
    dired = QtCore.Signal(str)
    commented = QtCore.Signal(str)
    newed = QtCore.Signal()
    saved = QtCore.Signal()
    loaded = QtCore.Signal(str, bool)

    def __init__(self, parent=None):
        super(SuiteView, self).__init__(parent=parent)
        self.setObjectName("SuiteView")

        panels = {
            "save": QtWidgets.QWidget(),
            "split": QtWidgets.QSplitter(),
            "suites": QtWidgets.QWidget(),
        }

        widgets = {
            "session": QtWidgets.QLabel("Current"),
            "name": QtWidgets.QLineEdit(),  # TODO: add name validator
            "dir": QtWidgets.QLineEdit(),
            "desc": QtWidgets.QTextEdit(),
            "save": QtWidgets.QPushButton("Save Suite"),
            "new": QtWidgets.QPushButton("New Suite"),
            # -splitter-
            "suites": QtWidgets.QTabWidget(),
            "saved": QtWidgets.QLabel("Saved"),
            "recent": SuiteLoadView(),
            "drafts": SuiteLoadView(),
            "visible": SuiteLoadView(),
        }

        widgets["name"].setPlaceholderText("Suite name..")
        widgets["dir"].setPlaceholderText("Suite dir..")
        widgets["desc"].setPlaceholderText("Suite description.. (optional)")
        widgets["desc"].setAcceptRichText(False)
        widgets["desc"].setTabChangesFocus(True)

        widgets["suites"].addTab(widgets["recent"], "Recent")
        widgets["suites"].addTab(widgets["drafts"], "Drafts")
        widgets["suites"].addTab(widgets["visible"], "Visible")

        layout = QtWidgets.QVBoxLayout(panels["save"])
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(widgets["session"])
        layout.addSpacing(4)
        layout.addWidget(widgets["name"])
        layout.addWidget(widgets["dir"])
        layout.addWidget(widgets["desc"])
        layout.addWidget(widgets["save"])
        layout.addWidget(widgets["new"])
        layout.setSpacing(2)

        layout = QtWidgets.QVBoxLayout(panels["suites"])
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(widgets["saved"])
        layout.addWidget(widgets["suites"])
        layout.addSpacing(4)

        panels["split"].setOrientation(QtCore.Qt.Vertical)
        panels["split"].addWidget(panels["save"])
        panels["split"].addWidget(panels["suites"])

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(2, 4, 2, 2)
        layout.addWidget(panels["split"])

        panels["split"].setStretchFactor(0, 20)
        panels["split"].setStretchFactor(1, 80)

        widgets["name"].textChanged.connect(self.named.emit)
        widgets["dir"].textChanged.connect(self.dired.emit)
        widgets["desc"].textChanged.connect(self.on_description_changed)
        widgets["new"].clicked.connect(self.newed.emit)
        widgets["save"].clicked.connect(self.saved.emit)
        widgets["recent"].loaded.connect(self.on_loaded)
        widgets["drafts"].loaded.connect(self.on_loaded)
        widgets["visible"].loaded.connect(self.on_loaded)

        self._widgets = widgets
        self._panels = panels

    def on_description_changed(self):
        text = self._widgets["desc"].toPlainText()
        self.commented.emit(text)

    def on_loaded(self, name, root, path, description):
        as_import = not bool(root)
        self.loaded.emit(path, as_import)
        self.change_suite(root, name, description)

    def change_suite(self, root, name, description):
        self._widgets["dir"].setText(root)
        self._widgets["name"].setText(name)
        self._widgets["desc"].setText(description)

    def set_model(self, recent, drafts, visible):
        self._widgets["recent"].set_model(recent)
        self._widgets["drafts"].set_model(drafts)
        self._widgets["visible"].set_model(visible)


class SuiteLoadView(QtWidgets.QWidget):
    loaded = QtCore.Signal(str, str, str, str)  # name, root, path, desc

    def __init__(self, parent=None):
        super(SuiteLoadView, self).__init__(parent=parent)
        self.setObjectName("SuiteLoadView")

        widgets = {
            "list": SlimTableView(),
            "view": QtWidgets.QWidget(),
            "desc": QtWidgets.QTextEdit(),
        }

        layout = QtWidgets.QHBoxLayout(widgets["view"])
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addStretch(stretch=50)
        layout.addWidget(widgets["desc"], stretch=50)
        layout.setSpacing(0)
        widgets["list"].setViewport(widgets["view"])

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(widgets["list"])
        layout.setSpacing(2)

        widgets["desc"].setReadOnly(True)
        widgets["list"].setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        widgets["list"].customContextMenuRequested.connect(self.on_rm_clicked)

        self._widgets = widgets

    def set_model(self, model):
        self._widgets["list"].setModel(model)
        sel_model = self._widgets["list"].selectionModel()
        sel_model.selectionChanged.connect(self.on_selection_changed)

    def on_selection_changed(self, selected, deselected):
        selected = selected.indexes()
        text = ""
        if selected:
            text = selected[0].data(role=SavedSuiteModel.DescriptionRole)
        self._widgets["desc"].setText(text)

    def on_rm_clicked(self, position):
        index = self._widgets["list"].indexAt(position)

        if not index.isValid():
            # Clicked outside any item
            return

        menu = QtWidgets.QMenu(self)
        open_ = QtWidgets.QAction("Open suite (loaded)", menu)
        import_ = QtWidgets.QAction("Open suite (import)", menu)
        explore = QtWidgets.QAction("Show in Explorer", menu)

        def on_open():
            data = index.data(role=SavedSuiteModel.ItemRole)
            self.loaded.emit(data["name"],
                             data["root"],
                             data["path"],
                             data["description"])

        def on_import():
            data = index.data(role=SavedSuiteModel.ItemRole)
            self.loaded.emit(data["name"],
                             "",  # root path is not required on import
                             data["path"],
                             data["description"])

        def on_explore():
            data = index.data(role=SavedSuiteModel.ItemRole)
            util.open_file_location(data["file"])

        open_.triggered.connect(on_open)
        import_.triggered.connect(on_import)
        explore.triggered.connect(on_explore)

        menu.addAction(open_)
        menu.addAction(import_)
        menu.addAction(explore)

        menu.move(QtGui.QCursor.pos())
        menu.show()