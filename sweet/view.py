
from .vendor.Qt5 import QtCore, QtGui, QtWidgets

from .version import version
from .common.view import Spoiler
from .search.view import PackageView
from .sphere.view import SphereView, ContextView
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
            "split": QtWidgets.QSplitter(),
            "page": QtWidgets.QTabWidget(),
        }

        pages = {
            "package": QtWidgets.QWidget(),
            "suite": QtWidgets.QWidget(),
            "context": QtWidgets.QWidget(),
            "preference": QtWidgets.QWidget(),
        }

        widgets = {
            "package": PackageView(),
            "sphere": SphereView(),
        }

        widgets["package"].set_model(ctrl.models["package"])
        widgets["package"].init_column_width()

        # layouts..
        panels["page"].addTab(pages["package"], "Package")
        panels["page"].addTab(pages["suite"], "Suite")
        panels["page"].addTab(pages["context"], "Context")
        panels["page"].addTab(pages["preference"], "Preference")

        panels["split"].setOrientation(QtCore.Qt.Horizontal)
        panels["split"].addWidget(panels["page"])
        panels["split"].addWidget(widgets["sphere"])

        layout = QtWidgets.QHBoxLayout(pages["package"])
        layout.addWidget(widgets["package"])

        layout = QtWidgets.QHBoxLayout(panels["body"])
        layout.addWidget(panels["split"])

        widgets["sphere"].suite_named.connect(ctrl.on_suite_named)
        widgets["sphere"].suite_saved.connect(ctrl.on_suite_saved)
        widgets["sphere"].context_drafted.connect(self.on_context_drafted)

        self._ctrl = ctrl
        self._panels = panels
        self._pages = pages
        self._widgets = widgets

        self.setCentralWidget(panels["body"])
        self.setFocus()

    def on_context_drafted(self):
        ctrl = self._ctrl
        sphere = self._widgets["sphere"]

        view = ContextView()
        id_ = view.id()
        # tracking context by widget object's id
        ctrl.register_context_draft(id_)

        view.setup_tool_view(model=ctrl.models["contextTool"][id_])
        view.setup_request_completer(model=ctrl.models["package"])

        spoiler = Spoiler(title="* untitled")
        spoiler.set_content(view)
        spoiler.set_expanded(True)

        sphere.add_context(spoiler, id_)

        view.named.connect(lambda i, t: spoiler.set_title(t or "* untitled"))
        view.removed.connect(lambda i: sphere.remove_context(i))

        view.named.connect(ctrl.on_context_named)
        view.requested.connect(ctrl.on_context_requested)
        view.removed.connect(ctrl.on_context_removed)
        view.prefix_changed.connect(ctrl.on_context_prefix_changed)
        view.suffix_changed.connect(ctrl.on_context_suffix_changed)
        view.alias_changed.connect(ctrl.on_context_tool_alias_changed)
        view.hide_changed.connect(ctrl.on_context_tool_hide_changed)

    def showEvent(self, event):
        super(Window, self).showEvent(event)
        splitter = self._panels["split"]
        self._ctrl.store("default/geometry", self.saveGeometry())
        self._ctrl.store("default/windowState", self.saveState())
        self._ctrl.store("default/windowSplitter", splitter.saveState())

        if self._ctrl.retrieve("geometry"):
            self.restoreGeometry(self._ctrl.retrieve("geometry"))
            self.restoreState(self._ctrl.retrieve("windowState"))
            splitter.restoreState(self._ctrl.retrieve("windowSplitter"))

    def closeEvent(self, event):
        splitter = self._panels["split"]
        self._ctrl.store("geometry", self.saveGeometry())
        self._ctrl.store("windowState", self.saveState())
        self._ctrl.store("windowSplitter", splitter.saveState())
        return super(Window, self).closeEvent(event)
