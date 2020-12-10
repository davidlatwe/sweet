
from .vendor.Qt5 import QtCore, QtGui, QtWidgets

from .version import version
from .common.view import Spoiler
from .search.view import PackageView
from .sphere.view import SphereView, ContextView
from .solve.view import SuiteContextTab, ContextResolveView
from .suite.view import SuiteView
from . import sweetconfig, resources as res


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
            "package": PackageView(),
            "suite": SuiteView(),
            "context": SuiteContextTab(),
            "preference": QtWidgets.QWidget(),
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
        pages["suite"].set_model(recent=ctrl.models["recent"],
                                 drafts=ctrl.models["drafts"],
                                 visible=ctrl.models["visible"])

        options = sweetconfig.suite_save_options()
        if options is not None:
            storage = QtCore.QSettings(QtCore.QSettings.IniFormat,
                                       QtCore.QSettings.UserScope,
                                       "Sweet", "saveOptions")
            pages["suite"].setup_save_options(options, storage)

        # signals..
        pages["suite"].named.connect(ctrl.on_suite_named)
        pages["suite"].rooted.connect(ctrl.on_suite_rooted)
        pages["suite"].commented.connect(ctrl.on_suite_commented)
        pages["suite"].newed.connect(self.on_suite_newed)
        pages["suite"].saved.connect(ctrl.on_suite_saved)
        pages["suite"].loaded.connect(ctrl.on_suite_loaded)
        widgets["sphere"].context_drafted.connect(self.on_context_drafted)
        ctrl.suite_changed.connect(pages["suite"].change_suite)
        ctrl.context_removed.connect(self.on_context_removed)
        ctrl.context_loaded.connect(self.on_context_loaded)
        if options is not None:
            options.changed.connect(ctrl.on_option_parser_changed)

        self._ctrl = ctrl
        self._panels = panels
        self._pages = pages
        self._widgets = widgets

        self.setCentralWidget(panels["body"])
        self.setFocus()

        # set default root
        default_root = sweetconfig.default_root() or ""
        self._pages["suite"].change_suite(default_root, None, None)
        # adjust column
        self._pages["package"].init_column_width()
        # show suite page on launch
        self._panels["page"].setCurrentIndex(2)
        # create one draft context on launch
        self.add_context_draft()

    def on_suite_newed(self):
        self._ctrl.clear_suite()
        self.add_context_draft()

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
