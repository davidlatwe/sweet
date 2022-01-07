
from ._vendor.Qt5 import QtCore, QtWidgets
from . import app, pages


class MainWindow(QtWidgets.QMainWindow):

    def __init__(self, state):
        """
        :param state:
        :type state: app.State
        """
        super(MainWindow, self).__init__(flags=QtCore.Qt.Window)

        body = QtWidgets.QWidget()

        tabs = QtWidgets.QTabWidget()
        tabs.addTab(pages.SuitePage(), "Suite Editor")
        tabs.addTab(pages.PreferencePage(state), "Preferences")

        layout = QtWidgets.QHBoxLayout(body)
        layout.addWidget(tabs)

        self._body = body
        self._state = state
        self._splitters = {
            s.objectName(): s
            for s in body.findChildren(QtWidgets.QSplitter) if s.objectName()
        }

        self.setCentralWidget(body)
        self.statusBar().show()  # todo: connect messages

    def find(self, widget_cls, name=None):
        return self._body.findChild(widget_cls, name)

    def reset_layout(self):
        with self._state.group("default"):
            self._state.restore_layout(self, "mainWindow", keep_geo=True)
            for key, split in self._splitters.items():
                self._state.restore_layout(split, key)

    def showEvent(self, event):
        super(MainWindow, self).showEvent(event)

        with self._state.group("default"):  # for resetting layout
            self._state.preserve_layout(self, "mainWindow")
            for key, split in self._splitters.items():
                self._state.preserve_layout(split, key)

        with self._state.group("current"):
            self._state.restore_layout(self, "mainWindow")
            for key, split in self._splitters.items():
                self._state.restore_layout(split, key)

    def closeEvent(self, event):
        with self._state.group("current"):
            self._state.preserve_layout(self, "mainWindow")
            for key, split in self._splitters.items():
                self._state.preserve_layout(split, key)

        return super(MainWindow, self).closeEvent(event)