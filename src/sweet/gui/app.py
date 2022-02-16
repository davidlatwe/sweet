
import os
import sys
import logging
import signal as py_signal
from typing import Optional
from importlib import reload
from contextlib import contextmanager
from ._vendor.Qt5 import QtCore, QtWidgets
from . import control, window, pages, widgets, resources


if sys.platform == "darwin":
    os.environ["QT_MAC_WANTS_LAYER"] = "1"  # MacOS BigSur


log = logging.getLogger("sweet")


def launch(app_name="sweet-gui"):
    """GUI entry point

    :param app_name: Application name. Used to compose the location of current
        user specific settings file. Default is "sweet-gui".
    :type app_name: str or None
    :return: QApplication exit code
    :rtype: int
    """
    ses = Session(app_name=app_name)
    ses.show()
    return ses.app.exec_()


class Session(object):

    def __init__(self, app_name="sweet-gui"):
        app = QtWidgets.QApplication.instance()
        if app is None:
            app = QtWidgets.QApplication([])
            app.setStyle(AppProxyStyle())

            # allow user to interrupt with Ctrl+C
            def sigint_handler(signals, frame):
                sys.exit(app.exit(-1))

            py_signal.signal(py_signal.SIGINT, sigint_handler)

        # sharpen icons/images
        # * the .svg file ext is needed in file path for Qt to auto scale it.
        # * without file ext given for svg file, may need to hard-coding attr
        #   like width/height/viewBox attr in that svg file.
        # * without the Qt attr below, .svg may being rendered as they were
        #   low-res.
        app.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps)

        # init

        storage = QtCore.QSettings(QtCore.QSettings.IniFormat,
                                   QtCore.QSettings.UserScope,
                                   app_name, "preferences")
        print("Preference file: %s" % storage.fileName())

        state = State(storage=storage)
        resources.load_themes()
        ctrl = control.Controller()
        view_ = window.MainWindow(state=state)

        # signals

        suite_head = view_.find(widgets.SuiteHeadWidget)
        context_list = view_.find(widgets.ContextListWidget)
        stacked_request = view_.find(widgets.StackedRequestWidget)
        stacked_resolve = view_.find(widgets.StackedResolveWidget)
        tool_stack = view_.find(widgets.ContextToolTreeWidget)
        tool_stack_model = tool_stack.model()
        installed_pkg = view_.find(widgets.InstalledPackagesWidget)
        installed_pkg_model = installed_pkg.model()
        storage_suite = view_.find(widgets.SuiteInsightWidget)
        storage_view = view_.find(widgets.SuiteBranchWidget)
        storage_model = storage_view.model()
        preference = view_.find(pages.PreferencePage)
        busy_filter = widgets.BusyEventFilterSingleton()

        # model -> control
        tool_stack_model.alias_changed.connect(ctrl.on_tool_alias_changed)
        tool_stack_model.hidden_changed.connect(ctrl.on_tool_hidden_changed)

        # view -> control
        context_list.added.connect(ctrl.on_add_context_clicked)
        context_list.dropped.connect(ctrl.on_drop_context_clicked)
        context_list.reordered.connect(ctrl.on_context_item_moved)
        context_list.renamed.connect(ctrl.on_rename_context_clicked)
        stacked_request.requested.connect(ctrl.on_resolve_context_clicked)
        stacked_request.prefix_changed.connect(ctrl.on_context_prefix_changed)
        stacked_request.suffix_changed.connect(ctrl.on_context_suffix_changed)
        installed_pkg.refreshed.connect(ctrl.on_installed_pkg_scan_clicked)
        suite_head.new_clicked.connect(ctrl.on_suite_new_clicked)
        suite_head.save_clicked.connect(ctrl.on_suite_save_clicked)
        storage_view.suite_load_clicked.connect(ctrl.on_suite_load_clicked)
        stacked_request.request_edited.connect(ctrl.on_request_edited)
        stacked_resolve.stash_clicked.connect(ctrl.on_stash_clicked)
        storage_view.suite_selected.connect(ctrl.on_saved_suite_selected)
        storage_view.refresh_clicked.connect(ctrl.on_suite_storage_scan_clicked)
        storage_suite.suites_archived.connect(ctrl.on_suites_archived)

        # control -> model
        ctrl.storage_scan_started.connect(storage_model.reset)
        ctrl.storage_scanned.connect(storage_model.add_saved_suites)
        ctrl.pkg_scan_started.connect(installed_pkg_model.reset)
        ctrl.pkg_families_scanned.connect(installed_pkg_model.add_families)
        ctrl.pkg_versions_scanned.connect(installed_pkg_model.add_versions)
        ctrl.context_added.connect(tool_stack_model.on_context_added)
        ctrl.context_renamed.connect(tool_stack_model.on_context_renamed)
        ctrl.context_dropped.connect(tool_stack_model.on_context_dropped)
        ctrl.context_reordered.connect(tool_stack_model.on_context_reordered)
        ctrl.context_resolved.connect(tool_stack_model.on_context_resolved)
        ctrl.request_edited.connect(tool_stack_model.on_request_edited)
        ctrl.tools_updated.connect(tool_stack_model.update_tools)
        ctrl.suite_newed.connect(tool_stack_model.on_suite_newed)
        ctrl.suite_saved.connect(storage_model.add_one_saved_suite)

        # control -> view
        ctrl.storage_scan_started.connect(storage_suite.on_refreshed)
        ctrl.suite_newed.connect(stacked_request.on_suite_newed)
        ctrl.suite_newed.connect(stacked_resolve.on_suite_newed)
        ctrl.suite_newed.connect(context_list.on_suite_newed)
        ctrl.suite_newed.connect(suite_head.on_suite_newed)
        ctrl.suite_saved.connect(suite_head.on_suite_saved)
        ctrl.suite_save_failed.connect(suite_head.on_suite_save_failed)
        ctrl.suite_loaded.connect(suite_head.on_suite_loaded)
        ctrl.suite_loaded.connect(lambda *_: view_.switch_tab(1))  # editor
        ctrl.suite_archived.connect(storage_view.on_suite_archived)
        ctrl.suite_viewed.connect(storage_suite.on_suite_viewed)
        ctrl.context_added.connect(context_list.on_context_added)
        ctrl.context_added.connect(stacked_request.on_context_added)
        ctrl.context_added.connect(stacked_resolve.on_context_added)
        ctrl.context_renamed.connect(context_list.on_context_renamed)
        ctrl.context_renamed.connect(stacked_request.on_context_renamed)
        ctrl.context_renamed.connect(stacked_resolve.on_context_renamed)
        ctrl.context_dropped.connect(context_list.on_context_dropped)
        ctrl.context_dropped.connect(stacked_request.on_context_dropped)
        ctrl.context_dropped.connect(stacked_resolve.on_context_dropped)
        ctrl.context_reordered.connect(context_list.on_context_reordered)
        ctrl.context_resolved.connect(stacked_request.on_context_resolved)
        ctrl.context_resolved.connect(stacked_resolve.on_context_resolved)
        ctrl.context_resolved.connect(context_list.on_context_resolved)
        ctrl.context_stashed.connect(stacked_resolve.on_context_stashed)
        ctrl.request_edited.connect(context_list.on_request_edited)

        # view -> view
        context_list.selected.connect(stacked_request.on_context_selected)
        context_list.selected.connect(stacked_resolve.on_context_selected)
        preference.changed.connect(self.on_preference_changed)
        view_.dark_toggled.connect(self.on_dark_toggled)

        # status bar messages
        ctrl.status_message.connect(view_.spoken)
        busy_filter.overwhelmed.connect(view_.spoken)
        stacked_resolve.env_hovered.connect(view_.spoken)

        self._app = app
        self._ctrl = ctrl
        self._view = view_
        self._state = state

        self.apply_theme()

    @property
    def app(self):
        return self._app

    @property
    def ctrl(self):
        return self._ctrl

    @property
    def view(self):
        return self._view

    @property
    def state(self):
        return self._state

    def on_dark_toggled(self, value):
        self._state.store_dark_mode(value)
        self.apply_theme(dark=value)
        self._view.on_status_changed(self._view.statusBar().currentMessage())

    def on_preference_changed(self, key, value):
        if key == "theme":
            self.apply_theme(value)
        elif key == "resetLayout":
            self._view.reset_layout()
        elif key == "reloadTheme":
            self.reload_theme()
        else:
            print("Unknown preference setting: %s" % key)

    def apply_theme(self, name=None, dark=None):
        view = self._view
        name = name or self.state.retrieve("theme")
        dark = self.state.retrieve_dark_mode() if dark is None else dark
        qss = resources.get_style_sheet(name, dark)
        view.setStyleSheet(qss)
        view.style().unpolish(view)
        view.style().polish(view)
        self.state.store("theme", resources.current_theme().name)

    def reload_theme(self):
        """For look-dev"""
        reload(resources)
        resources.load_themes()
        self.apply_theme()

    def show(self):
        view = self._view
        view.show()

        # If the window is minimized then un-minimize it.
        if view.windowState() & QtCore.Qt.WindowMinimized:
            view.setWindowState(QtCore.Qt.WindowActive)

        view.raise_()  # for MacOS
        view.activateWindow()  # for Windows

    def process(self, events=QtCore.QEventLoop.AllEvents):
        self._app.eventDispatcher().processEvents(events)

    def close(self):
        self._app.closeAllWindows()
        self._app.quit()


class State(object):
    """Store/re-store Application status in/between sessions"""

    def __init__(self, storage):
        """
        :param storage: An QtCore.QSettings instance for save/load settings
            between sessions.
        :type storage: QtCore.QSettings
        """
        self._storage = storage

    def _f(self, value):
        # Account for poor serialisation format
        true = ["2", "1", "true", True, 1, 2]
        false = ["0", "false", False, 0]

        if value in true:
            value = True

        if value in false:
            value = False

        if value and str(value).isnumeric():
            value = float(value)

        return value

    @contextmanager
    def group(self, key):
        self._storage.beginGroup(key)
        try:
            yield
        finally:
            self._storage.endGroup()

    def is_writeable(self):
        return self._storage.isWritable()

    def store(self, key, value):
        self._storage.setValue(key, value)

    def retrieve(self, key, default=None):
        value = self._storage.value(key)
        if value is None:
            value = default
        return self._f(value)

    def retrieve_dark_mode(self):
        return bool(self.retrieve("theme.on_dark"))

    def store_dark_mode(self, value):
        self.store("theme.on_dark", bool(value))

    def preserve_layout(self, widget, group):
        # type: (QtWidgets.QWidget, str) -> None
        if not self.is_writeable():
            log.warning("Application settings file is not writable: "
                        f"{self._storage.fileName()}")
            return

        self._storage.beginGroup(group)

        self.store("geometry", widget.saveGeometry())
        if hasattr(widget, "saveState"):
            self.store("state", widget.saveState())
        if hasattr(widget, "directory"):  # QtWidgets.QFileDialog
            self.store("directory", widget.directory())

        self._storage.endGroup()

    def restore_layout(self, widget, group, keep_geo=False):
        # type: (QtWidgets.QWidget, str, bool) -> None
        self._storage.beginGroup(group)

        keys = self._storage.allKeys()

        if not keep_geo and "geometry" in keys:
            widget.restoreGeometry(self.retrieve("geometry"))
        if "state" in keys and hasattr(widget, "restoreState"):
            widget.restoreState(self.retrieve("state"))
        if "directory" in keys and hasattr(widget, "setDirectory"):
            widget.setDirectory(self.retrieve("directory"))

        self._storage.endGroup()


class AppProxyStyle(QtWidgets.QProxyStyle):
    """For styling QComboBox
    https://stackoverflow.com/a/21019371
    """
    def styleHint(
            self,
            hint: QtWidgets.QStyle.StyleHint,
            option: Optional[QtWidgets.QStyleOption] = ...,
            widget: Optional[QtWidgets.QWidget] = ...,
            returnData: Optional[QtWidgets.QStyleHintReturn] = ...,) -> int:

        if hint == QtWidgets.QStyle.SH_ComboBox_Popup:
            return 0

        return super(AppProxyStyle, self).styleHint(
            hint, option, widget, returnData)
