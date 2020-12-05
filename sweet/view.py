
from Qt5 import QtCore, QtGui, QtWidgets

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
        }

        widgets = {
            "package": PackageView(),
            "sphere": SphereView(),
        }

        widgets["package"].set_model(ctrl.models["package"])
        widgets["package"].init_column_width()

        layout = QtWidgets.QHBoxLayout(panels["body"])
        layout.addWidget(widgets["package"])
        layout.addWidget(widgets["sphere"])

        widgets["sphere"].context_drafted.connect(self.on_context_drafted)
        widgets["sphere"].suite_saved.connect(ctrl.on_suite_saved)

        self._ctrl = ctrl
        self._panels = panels
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

        spoiler = Spoiler(title="untitled..")
        spoiler.set_content(view)
        spoiler.set_expanded(True)

        sphere.add_context(spoiler, id_)

        view.named.connect(lambda i, t: spoiler.set_title(t or "untitled.."))
        view.removed.connect(lambda i: sphere.remove_context(i))

        view.named.connect(ctrl.on_context_named)
        view.requested.connect(ctrl.on_context_requested)
        view.removed.connect(ctrl.on_context_removed)
        view.prefix_changed.connect(ctrl.on_context_prefix_changed)
        view.suffix_changed.connect(ctrl.on_context_suffix_changed)
        view.alias_changed.connect(ctrl.on_context_tool_alias_changed)
        view.hide_changed.connect(ctrl.on_context_tool_hide_changed)
