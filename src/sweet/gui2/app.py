
import os
import sys
from ..gui.vendor.Qt5 import QtCore, QtWidgets
from ..gui import resources
from . import control, view


def launch(app_name="sweet-gui"):
    """GUI entry point

    :param app_name: Application name. Used to compose the location of current
        user specific settings file. Default is "sweet-gui".
    :type app_name: str or None
    :return: QApplication exit code
    :rtype: int
    """
    ses = Session(app_name=app_name)
    return ses.app.exec_()


class Session(object):

    def __init__(self, app_name="sweet-gui"):

        if sys.platform == "darwin":
            os.environ["QT_MAC_WANTS_LAYER"] = "1"  # MacOS BigSur

        app = QtWidgets.QApplication.instance()  # noqa
        app = app or QtWidgets.QApplication([])

        storage = QtCore.QSettings(QtCore.QSettings.IniFormat,
                                   QtCore.QSettings.UserScope,
                                   app_name, "preferences")
        print("Preference file: %s" % storage.fileName())

        state = State(storage=storage)
        ctrl = control.Controller(state=state)
        view_ = view.MainWindow(state=state)

        resources.load_themes()
        qss = resources.load_theme(name=state.retrieve("theme"))
        view_.setStyleSheet(qss)

        self._app = app
        self._ctrl = ctrl
        self._view = view_

        self._build_connections()

    @property
    def app(self):
        return self._app

    @property
    def ctrl(self):
        return self._ctrl

    @property
    def view(self):
        return self._view

    def _build_connections(self):
        pass


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

    def store(self, key, value):
        self._storage.setValue(key, value)

    def retrieve(self, key, default=None):
        value = self._storage.value(key)
        if value is None:
            value = default
        return self._f(value)
