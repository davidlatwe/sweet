
from ..gui.vendor.Qt5 import QtCore, QtWidgets
from . import app


class MainWindow(QtWidgets.QMainWindow):

    def __init__(self, state):
        super(MainWindow, self).__init__(flags=QtCore.Qt.Window)
        self._state = state

    @property
    def state(self):
        # type: () -> app.State
        return self._state

    def showEvent(self, event):
        super(MainWindow, self).showEvent(event)
        # splitter = self._panels["split"]

        with self.state.group("default"):  # for resetting layout
            self.state.preserve_layout(self, "mainWindow")
            # self.state.preserve_layout(splitter, "mainSplitter")

        with self.state.group("current"):
            self.state.restore_layout(self, "mainWindow")
            # self.state.restore_layout(splitter, "mainSplitter")

    def closeEvent(self, event):
        # splitter = self._panels["split"]

        with self.state.group("current"):
            self.state.preserve_layout(self, "mainWindow")
            # self.state.preserve_layout(splitter, "mainSplitter")

        return super(MainWindow, self).closeEvent(event)


"""Notes

Current Suite
Suite View: context and tools
Context Resolve
Context View: packages, environment

Saved Suites: with context-tool list, search bar (don't use tab)
Preference
Package Lookup
"""
