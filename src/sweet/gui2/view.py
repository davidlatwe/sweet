
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

        suite_tab = QtWidgets.QSplitter()
        suite_tab.setOrientation(QtCore.Qt.Horizontal)
        suite_tab.addWidget(resolve_page)
        suite_tab.addWidget(suite_page)

        tabs = QtWidgets.QTabWidget()
        tabs.addTab(suite_tab, "Suite Editor")

        layout = QtWidgets.QHBoxLayout(body)
        layout.addWidget(tabs)

        self._body = body
        self._state = state
        self._splitters = {
            "suiteEditSplit": suite_tab
        }

        self.setCentralWidget(body)

    def find(self, widget_cls, name=None):
        return self._body.findChild(widget_cls, name)

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


"""Notes

Current Suite
Tools View: context and tools
Context Resolve
Context View: packages, environment

Saved Suites: with context-tool list, search bar (don't use tab)
Preference
Package Lookup
"""
