
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
    if sys.platform == "darwin":
        os.environ["QT_MAC_WANTS_LAYER"] = "1"  # MacOS BigSur

    app = QtWidgets.QApplication.instance() # noqa
    app = app or QtWidgets.QApplication([])

    storage = QtCore.QSettings(QtCore.QSettings.IniFormat,
                               QtCore.QSettings.UserScope,
                               app_name, "preferences")
    print("Preference file: %s" % storage.fileName())

    state = State(storage=storage)
    ctrl = control.Controller(state=state)
    window = view.MainWindow(ctrl=ctrl)

    resources.load_themes()
    qss = resources.load_theme(name=state.retrieve("theme"))
    window.setStyleSheet(qss)

    window.show()

    return app.exec_()


def init():
    # todo: init controller and stuff here, good for testing.
    pass


class State(object):  # todo: or this should be "Session" ?
    """Store/re-store Application status in/between sessions"""

    _non = object()  # no value

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

    @property
    def non(self):
        return self._non

    def s_geometry(self, val=_non):
        pass
