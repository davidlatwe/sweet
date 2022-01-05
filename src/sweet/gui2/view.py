
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
        suite_page = pages.SuitePage()
        resolve_page = pages.ResolvePage()

        layout = QtWidgets.QHBoxLayout(body)
        layout.addWidget(resolve_page)
        layout.addWidget(suite_page)

        self._body = body
        self._state = state

        self.setCentralWidget(body)

    def find(self, widget_cls, name=None):
        return self._body.findChild(widget_cls, name)

    def showEvent(self, event):
        super(MainWindow, self).showEvent(event)
        # splitter = self._panels["split"]

        with self._state.group("default"):  # for resetting layout
            self._state.preserve_layout(self, "mainWindow")
            # self._state.preserve_layout(splitter, "mainSplitter")

        with self._state.group("current"):
            self._state.restore_layout(self, "mainWindow")
            # self._state.restore_layout(splitter, "mainSplitter")

    def closeEvent(self, event):
        # splitter = self._panels["split"]

        with self._state.group("current"):
            self._state.preserve_layout(self, "mainWindow")
            # self._state.preserve_layout(splitter, "mainSplitter")

        return super(MainWindow, self).closeEvent(event)


"""Notes

Current Suite
Tools View: context and tools
Context Resolve
Context View: packages, environment

Saved Suites: with context-tool list, search bar (don't use tab)
Preference
Package Lookup
"""
