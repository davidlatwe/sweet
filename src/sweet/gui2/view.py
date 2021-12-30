
from ..gui.vendor.Qt5 import QtCore, QtWidgets


class MainWindow(QtWidgets.QMainWindow):

    def __init__(self, state):
        super(MainWindow, self).__init__(flags=QtCore.Qt.Window)
        self._state = state

    def showEvent(self, event):
        super(MainWindow, self).showEvent(event)
        state = self._state
        # splitter = self._panels["split"]
        state.store("default/geometry", self.saveGeometry())
        state.store("default/windowState", self.saveState())
        # state.store("default/windowSplitter", splitter.saveState())

        if state.retrieve("geometry"):
            self.restoreGeometry(state.retrieve("geometry"))
            self.restoreState(state.retrieve("windowState"))
            # splitter.restoreState(state.retrieve("windowSplitter"))

    def closeEvent(self, event):
        state = self._state
        # splitter = self._panels["split"]
        state.store("geometry", self.saveGeometry())
        state.store("windowState", self.saveState())
        # state.store("windowSplitter", splitter.saveState())
        return super(MainWindow, self).closeEvent(event)
