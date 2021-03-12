
import os
from rez.config import config as rezconfig
from .vendor.Qt5 import QtCore, QtWidgets
from ._version import version
from .common.view import Spoiler, SimpleDialog
from .search.view import PackageView
from .sphere.view import SphereView, ContextView
from .solve.view import SuiteContextTab, ContextResolveView
from .suite.view import SuiteView
from .preference import Preference
from . import util, resources as res


sweetconfig = rezconfig.plugins.application.sweet


class Window(QtWidgets.QMainWindow):
    title = "Sweet %s" % version

    def __init__(self, ctrl, parent=None):
        super(Window, self).__init__(parent)
        self.setWindowTitle(self.title)
        self.setAttribute(QtCore.Qt.WA_StyledBackground)
        self.setWindowIcon(res.icon("images", "calculator"))  # TODO: logo

        panels = {
            "body": QtWidgets.QWidget(),
            "split": QtWidgets.QSplitter(),
            "page": QtWidgets.QTabWidget(),
        }

        pages = {
            "package": PackageView(),
            "suite": SuiteView(),
            "context": SuiteContextTab(),
            "preference": Preference(ctrl.state),
        }

        widgets = {
            "sphere": SphereView(),
        }

        # layouts..
        panels["page"].addTab(pages["package"], "Package")
        panels["page"].addTab(pages["context"], "Context")
        panels["page"].addTab(pages["suite"], "Suite")
        panels["page"].addTab(pages["preference"], "Preference")

        panels["split"].setOrientation(QtCore.Qt.Horizontal)
        panels["split"].addWidget(panels["page"])
        panels["split"].addWidget(widgets["sphere"])

        layout = QtWidgets.QHBoxLayout(panels["body"])
        layout.addWidget(panels["split"])

        # setup..
        pages["package"].set_model(ctrl.models["package"])
        pages["suite"].add_suite_list("recent", ctrl.models["recent"])
        for key in ctrl.state["suiteSaveRoots"].keys():
            is_default = key == sweetconfig.default_root
            pages["suite"].add_suite_root(key, is_default)
            pages["suite"].add_suite_list(key, ctrl.models["saved"][key])

        # signals..
        pages["suite"].named.connect(ctrl.on_suite_named)
        pages["suite"].rooted.connect(ctrl.on_suite_rooted)
        pages["suite"].commented.connect(ctrl.on_suite_commented)
        pages["suite"].newed.connect(self.on_suite_newed)
        pages["suite"].opened.connect(self.on_suite_opened)
        pages["suite"].saved.connect(self.on_suite_saved)
        pages["suite"].loaded.connect(ctrl.on_suite_loaded)
        widgets["sphere"].context_drafted.connect(self.on_context_drafted)
        ctrl.suite_changed.connect(pages["suite"].on_suite_changed)
        ctrl.context_removed.connect(self.on_context_removed)
        ctrl.context_loaded.connect(self.on_context_loaded)
        pages["preference"].changed.connect(self.on_preference_changed)

        self._ctrl = ctrl
        self._panels = panels
        self._pages = pages
        self._widgets = widgets

        self.setCentralWidget(panels["body"])
        self.setFocus()

        # set default root
        default_root = ctrl.default_root()
        self._pages["suite"].on_suite_changed(default_root, None, None)
        # adjust column
        self._pages["package"].init_column_width()
        # show suite page on launch
        self._panels["page"].setCurrentIndex(2)
        # create one draft context on launch
        self.add_context_draft()

    def on_suite_newed(self):
        self._ctrl.clear_suite()
        self.add_context_draft()

    def on_suite_saved(self):
        self._ctrl.on_suite_saved()

    def on_suite_opened(self):
        path = self.show_file_dialog("openSuite")
        if path:

            if not os.path.isfile(os.path.join(path, "suite.yaml")):
                print("No 'suite.yaml' found, not a suite dir.")
                return

            action = self._ctrl.state["suiteOpenAs"]
            if action == "Ask":
                dialog = SimpleDialog(message="Open existing suite as ..",
                                      options=["Loaded", "Import"],
                                      parent=self)
                if dialog.exec_():
                    as_import = dialog.answer() == "Import"
                else:
                    return

            else:
                as_import = action == "Import"

            path = util.normpath(path)
            self._ctrl.load_suite(path, as_import)

    def on_context_drafted(self):
        self.add_context_draft(focus=True)

    def on_context_loaded(self, context_data, requests):
        self.add_context_draft(context_data, requests)

    def add_context_draft(self, context_data=None, requests=None, focus=False):
        ctrl = self._ctrl
        sphere = self._widgets["sphere"]
        panel = self._panels["page"]
        page = self._pages["context"]
        untitled = "* untitled"

        view = ContextView()
        id_ = view.id()  # tracking context by widget's id
        ctrl.register_context_draft(id_)

        view.setup_tool_view(model=ctrl.models["contextTool"][id_])

        spoiler = Spoiler(title=untitled)
        spoiler.set_content(view)
        spoiler.set_expanded(True)
        sphere.add_context(spoiler, id_)

        tab = ContextResolveView(id_)
        tab.setup_request_completer(model=ctrl.models["package"])
        tab.set_models(packages=ctrl.models["contextPackages"][id_],
                       environment=ctrl.models["contextEnvironment"][id_])
        page.addTab(tab, untitled)

        # signals..
        view.named.connect(lambda i, t: spoiler.set_title(t or untitled))
        view.named.connect(lambda i, t: page.set_title(tab, t or untitled))
        view.named.connect(ctrl.on_context_named)
        view.bumped.connect(lambda i: sphere.bump_context(i))
        view.bumped.connect(ctrl.on_context_bumped)
        view.removed.connect(ctrl.on_context_removed)
        view.prefix_changed.connect(ctrl.on_context_prefix_changed)
        view.suffix_changed.connect(ctrl.on_context_suffix_changed)
        view.alias_changed.connect(ctrl.on_context_tool_alias_changed)
        view.hide_changed.connect(ctrl.on_context_tool_hide_changed)
        tab.requested.connect(ctrl.on_context_requested)

        def active_context_page():
            page.show_context(tab)
            panel.setCurrentIndex(1)  # context page
        view.jumped.connect(active_context_page)

        # show context resolve page on added
        if focus:
            active_context_page()

        # from loaded
        if context_data:
            view.load(context_data)
        if requests:
            tab.set_requests("\n".join(requests))
            tab.requested.emit(id_, requests)

    def on_context_removed(self, id_):
        self._widgets["sphere"].remove_context(id_)
        self._pages["context"].remove_context(id_)

    def on_preference_changed(self, name, value):

        if name == "theme":
            qss = res.load_theme(value)
            self.setStyleSheet(qss)
            self.style().unpolish(self)
            self.style().polish(self)

        elif name == "recentSuiteCount":
            self._ctrl.state["recentSuiteCount"] = value
            self._ctrl.defer_change_max_recent()

        elif name == "suiteOpenAs":
            self._ctrl.state["suiteOpenAs"] = value

    def show_file_dialog(self, namespace=None):
        state = self._ctrl.state
        dialog = QtWidgets.QFileDialog(self)
        if namespace and state.retrieve("%s/windowState" % namespace):
            # somehow directory won't get restored with restoreState
            dialog.setDirectory(state.retrieve("%s/directory" % namespace))
            dialog.restoreState(state.retrieve("%s/windowState" % namespace))

        path = dialog.getExistingDirectory()
        if namespace:
            state.store("%s/directory" % namespace, dialog.directory())
            state.store("%s/windowState" % namespace, dialog.saveState())

        return path

    def showEvent(self, event):
        super(Window, self).showEvent(event)
        state = self._ctrl.state
        splitter = self._panels["split"]
        state.store("default/geometry", self.saveGeometry())
        state.store("default/windowState", self.saveState())
        state.store("default/windowSplitter", splitter.saveState())

        if state.retrieve("geometry"):
            self.restoreGeometry(state.retrieve("geometry"))
            self.restoreState(state.retrieve("windowState"))
            splitter.restoreState(state.retrieve("windowSplitter"))

    def closeEvent(self, event):
        state = self._ctrl.state
        splitter = self._panels["split"]
        state.store("geometry", self.saveGeometry())
        state.store("windowState", self.saveState())
        state.store("windowSplitter", splitter.saveState())
        return super(Window, self).closeEvent(event)
