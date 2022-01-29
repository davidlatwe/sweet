
from ._vendor.Qt5 import QtCore, QtWidgets
from . import app, pages


class MainWindow(QtWidgets.QMainWindow):
    dark_toggled = QtCore.Signal(bool)

    def __init__(self, state):
        """
        :param state:
        :type state: app.State
        """
        super(MainWindow, self).__init__(flags=QtCore.Qt.Window)

        body = QtWidgets.QWidget()

        tabs = QtWidgets.QTabBar()
        stack = QtWidgets.QStackedWidget()
        tabs.setObjectName("MainTabs")
        stack.setObjectName("MainStack")

        tabs.addTab("Saved Suites")
        stack.addWidget(pages.StoragePage())
        tabs.addTab("Suite Editor")
        stack.addWidget(pages.SuitePage())
        tabs.addTab("Preferences")
        stack.addWidget(pages.PreferencePage(state))

        buttons = QtWidgets.QWidget()
        buttons.setObjectName("ButtonBelt")
        dark_btn = QtWidgets.QPushButton()
        dark_btn.setObjectName("DarkSwitch")
        dark_btn.setCheckable(True)

        layout = QtWidgets.QHBoxLayout(buttons)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.addWidget(dark_btn)

        layout = QtWidgets.QGridLayout(body)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(tabs, 0, 0, 1, 1,
                         QtCore.Qt.AlignLeft | QtCore.Qt.AlignBottom)
        layout.addWidget(buttons, 0, 1, 1, 1, QtCore.Qt.AlignRight)
        layout.addWidget(stack, 1, 0, 1, 2)

        tabs.currentChanged.connect(stack.setCurrentIndex)
        dark_btn.toggled.connect(self.dark_toggled.emit)

        self._body = body
        self._tabs = tabs
        self._state = state
        self._splitters = {
            s.objectName(): s
            for s in body.findChildren(QtWidgets.QSplitter) if s.objectName()
        }

        self.statusBar().show()
        self.setCentralWidget(body)
        self.setContentsMargins(6, 6, 6, 6)

        dark_btn.setChecked(state.retrieve_dark_mode())
        tabs.setCurrentIndex(1)  # editor

    @QtCore.Slot()  # noqa
    def spoken(self, message):
        self.statusBar().showMessage(message, 2000)

    def find(self, widget_cls, name=None):
        return self._body.findChild(widget_cls, name)

    def switch_tab(self, index):
        self._tabs.setCurrentIndex(index)

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
