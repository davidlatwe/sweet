
import os
import sys
import signal as py_signal
from contextlib import contextmanager
from ._vendor.Qt5 import QtCore, QtWidgets
from . import control, window, pages, widgets, resources


if sys.platform == "darwin":
    os.environ["QT_MAC_WANTS_LAYER"] = "1"  # MacOS BigSur


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

            # allow user to interrupt with Ctrl+C
            def sigint_handler(signals, frame):
                sys.exit(app.exit(-1))

            py_signal.signal(py_signal.SIGINT, sigint_handler)

        # init

        storage = QtCore.QSettings(QtCore.QSettings.IniFormat,
                                   QtCore.QSettings.UserScope,
                                   app_name, "preferences")
        print("Preference file: %s" % storage.fileName())

        state = State(storage=storage)

        resources.load_themes()
        qss = resources.load_theme(name=state.retrieve("theme"))

        ctrl = control.Controller(state=state)
        view_ = window.MainWindow(state=state)
        view_.setStyleSheet(qss)

        # signals

        context_list = view_.find(widgets.ContextListWidget)
        stacked_resolve = view_.find(widgets.StackedResolveView)
        request_editor = view_.find(widgets.RequestEditor)
        installed_pkg = view_.find(widgets.InstalledPackagesWidget)
        installed_pkg_model = installed_pkg.model()
        preference = view_.find(pages.PreferencePage)

        # view -> control
        context_list.added.connect(ctrl.on_add_context_clicked)
        context_list.dropped.connect(ctrl.on_drop_context_clicked)
        context_list.reordered.connect(ctrl.on_context_item_moved)
        context_list.renamed.connect(ctrl.on_rename_context_clicked)
        request_editor.requested.connect(ctrl.on_resolve_context_clicked)

        # control -> view
        ctrl.pkg_scan_started.connect(installed_pkg_model.clear)
        ctrl.pkg_scan_started.connect(lambda: print("start pkg scanning"))
        ctrl.pkg_families_scanned.connect(installed_pkg_model.add_families)
        ctrl.pkg_families_scanned.connect(request_editor.on_families_scanned)
        ctrl.pkg_versions_scanned.connect(installed_pkg_model.add_versions)
        ctrl.pkg_versions_scanned.connect(request_editor.on_versions_scanned)
        ctrl.pkg_scan_ended.connect(lambda: print("all pkg scanned"))
        ctrl.context_added.connect(context_list.on_context_added)
        ctrl.context_added.connect(stacked_resolve.on_context_added)
        ctrl.context_renamed.connect(context_list.on_context_renamed)
        ctrl.context_renamed.connect(stacked_resolve.on_context_renamed)
        ctrl.context_dropped.connect(context_list.on_context_dropped)
        ctrl.context_dropped.connect(stacked_resolve.on_context_dropped)
        ctrl.context_reordered.connect(context_list.on_context_reordered)

        # view -> view
        context_list.selected.connect(stacked_resolve.on_context_selected)
        preference.changed.connect(self.on_preference_changed)

        self._app = app
        self._ctrl = ctrl
        self._view = view_
        self._state = state

        ctrl.scan_installed_packages()

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

    def on_preference_changed(self, key, value):
        if key == "theme":
            self.apply_theme(value)
        elif key == "suiteOpenAs":
            pass  # self._ctrl.state["suiteOpenAs"] = value
        elif key == "resetLayout":
            self._view.reset_layout()
        elif key == "reloadTheme":
            self.apply_theme(self._state.retrieve("theme"))
        else:
            print("Unknown preference setting: %s" % key)

    def apply_theme(self, name):
        view = self._view
        qss = resources.load_theme(name)
        view.setStyleSheet(qss)
        view.style().unpolish(view)
        view.style().polish(view)

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

    def preserve_layout(self, widget, group):
        # type: (QtWidgets.QWidget, str) -> None
        if not self.is_writeable():
            # todo: prompt warning
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
