
from ..vendor.Qt5 import QtCore, QtGui, QtWidgets
from ..common.view import SlimTableView, QArgParserDialog
from .model import SavedSuiteModel
from .. import util


class SuiteView(QtWidgets.QWidget):

    # TODO:
    #   batch context re-resolve, match by resolved package (another window ?)

    named = QtCore.Signal(str)
    rooted = QtCore.Signal(str)
    commented = QtCore.Signal(str)
    optioned = QtCore.Signal(dict)
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
            "desc": QtWidgets.QTextEdit(),
            "operate": QtWidgets.QWidget(),
            "dest": QtWidgets.QLineEdit(),
            "roots": QtWidgets.QPushButton(),
            "opts": QtWidgets.QPushButton(" More"),
            "save": QtWidgets.QPushButton(" Save"),
            "new": QtWidgets.QPushButton(" New"),
            # -splitter-
            "suites": QtWidgets.QTabWidget(),
            "saved": QtWidgets.QLabel("Saved"),
            # additional option dialog
            "dialog": QArgParserDialog(self),
            # location selecting menu
            "actions": QtWidgets.QActionGroup(self),
        }
        widgets["opts"].setObjectName("SuiteOptionButton")
        widgets["save"].setObjectName("SuiteSaveButton")
        widgets["new"].setObjectName("SuiteNewButton")
        widgets["roots"].setObjectName("SuiteRootsButton")

        widgets["name"].setPlaceholderText("Suite dir name..")
        widgets["desc"].setPlaceholderText("Suite description.. (optional)")
        widgets["desc"].setAcceptRichText(False)
        widgets["desc"].setTabChangesFocus(True)
        widgets["dest"].setReadOnly(True)

        widgets["dialog"].setWindowTitle("Suite Save Options")
        widgets["opts"].setEnabled(False)
        widgets["opts"].setVisible(False)

        widgets["roots"].setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        widgets["actions"].setExclusive(True)

        layout = QtWidgets.QGridLayout(widgets["operate"])
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(widgets["roots"], 0, 0)
        layout.addWidget(widgets["dest"], 0, 1, 1, -1)
        layout.addItem(QtWidgets.QSpacerItem(1, 1), 1, 0, 1, 3)
        layout.addWidget(widgets["opts"], 1, 3)
        layout.addWidget(widgets["save"], 1, 4)
        layout.addWidget(widgets["new"], 1, 5)
        layout.setSpacing(2)

        layout = QtWidgets.QVBoxLayout(panels["save"])
        layout.setContentsMargins(0, 0, 0, 12)
        layout.addWidget(widgets["session"])
        layout.addSpacing(4)
        layout.addWidget(widgets["name"])
        layout.addWidget(widgets["desc"])
        layout.addWidget(widgets["operate"])
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

        # signals..
        widgets["name"].textChanged.connect(self.named.emit)
        widgets["desc"].textChanged.connect(self.on_description_changed)
        widgets["opts"].clicked.connect(self.on_dialog_shown)
        widgets["save"].clicked.connect(self.saved.emit)
        widgets["new"].clicked.connect(self.newed.emit)
        widgets["roots"].clicked.connect(self.on_roots_clicked)
        widgets["roots"].customContextMenuRequested.connect(
            self.on_roots_clicked
        )

        self._widgets = widgets
        self._panels = panels

    def setup_save_options(self, options, storage):
        self._widgets["opts"].setEnabled(True)
        self._widgets["opts"].setVisible(True)
        self._widgets["dialog"].install(options, storage)

    def on_dialog_shown(self):
        dialog = self._widgets["dialog"]
        default = dialog.read()

        if dialog.exec_():
            # accepted
            self.optioned.emit(dialog.read())
        else:
            # rejected/canceled
            dialog.write(default)
            self.optioned.emit(default)

    def on_destination_changed(self, path):
        self._widgets["dest"].setText(path)

    def on_description_changed(self):
        text = self._widgets["desc"].toPlainText()
        self.commented.emit(text)

    def on_loaded(self, root_key, path, as_import):
        self.loaded.emit(path, as_import)
        for action in self._widgets["actions"].actions():
            value = not as_import and (action.text() == root_key)
            action.setChecked(value)

    def on_roots_clicked(self):
        menu = QtWidgets.QMenu(self)

        for action in self._widgets["actions"].actions():
            menu.addAction(action)

        menu.move(QtGui.QCursor.pos())
        menu.show()

    def on_suite_changed(self, root, name, description):
        if root is not None:
            self._widgets["dest"].setText(root)
        if name is not None:
            self._widgets["name"].setText(name)
        if description is not None:
            self._widgets["desc"].setText(description)

    def add_suite_list(self, name, model):
        title = name.capitalize()
        view = SuiteLoadView(key=title)
        view.set_model(model)
        view.loaded.connect(self.on_loaded)
        self._widgets["suites"].addTab(view, title)

    def add_suite_root(self, name, is_default):
        title = name.capitalize()
        action = QtWidgets.QAction(title)
        action.setCheckable(True)
        action.setChecked(is_default)

        action.triggered.connect(lambda: self.rooted.emit(name))

        self._widgets["actions"].addAction(action)


class SuiteLoadView(QtWidgets.QWidget):
    loaded = QtCore.Signal(str, str, bool)  # root_key, path, as_import

    def __init__(self, key, parent=None):
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
        widgets["list"].setAlternatingRowColors(True)
        widgets["list"].setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        widgets["list"].customContextMenuRequested.connect(self.on_rm_clicked)

        self._widgets = widgets
        self._key = key

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
            self.loaded.emit(self._key, data["path"], False)

        def on_import():
            data = index.data(role=SavedSuiteModel.ItemRole)
            self.loaded.emit(self._key, data["path"], True)

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
