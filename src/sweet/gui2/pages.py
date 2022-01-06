
from ._vendor.Qt5 import QtCore, QtWidgets
from .widgets import (
    CurrentSuite,
    ContextStack,
    ToolStack,
    ResolvePanel,
)


class SuitePage(QtWidgets.QWidget):

    def __init__(self, *args, **kwargs):
        super(SuitePage, self).__init__(*args, **kwargs)

        current_suite = CurrentSuite()
        context_stack = ContextStack()
        tool_stack = ToolStack()

        splitter = QtWidgets.QSplitter()
        splitter.setOrientation(QtCore.Qt.Vertical)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(current_suite)
        splitter.addWidget(context_stack)
        splitter.addWidget(tool_stack)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(splitter)


class ResolvePage(QtWidgets.QWidget):

    def __init__(self, *args, **kwargs):
        super(ResolvePage, self).__init__(*args, **kwargs)

        switch = QtWidgets.QComboBox()
        stack = QtWidgets.QStackedWidget()

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(switch)
        layout.addWidget(stack)

        switch.currentIndexChanged.connect(stack.setCurrentIndex)

        self._switch = switch
        self._stack = stack

        self._add_panel_0()

    def on_context_added(self, ctx):
        name = ctx.name
        is_first = self._switch.count() == 0

        self._switch.insertItem(0, name)
        if is_first:
            panel = self._stack.widget(0)
            panel.set_name(name)
            panel.setEnabled(True)
        else:
            self.add_panel(name)
            self._switch.setCurrentIndex(0)

    def on_context_dropped(self, name):
        index = self._switch.findText(name)
        if index < 0:
            return  # should not happen

        self._switch.removeItem(index)
        is_empty = self._switch.count() == 0

        panel = self._stack.widget(index)
        self._stack.removeWidget(panel)
        if is_empty:
            self._add_panel_0()

    def add_panel(self, name, enabled=True):
        panel = ResolvePanel()
        panel.set_name(name)
        panel.setEnabled(enabled)

        self._stack.insertWidget(0, panel)

    def _add_panel_0(self):
        self.add_panel("", enabled=False)


class StoragePage(QtWidgets.QWidget):

    def __init__(self, *args, **kwargs):
        super(StoragePage, self).__init__(*args, **kwargs)


class PackagesPage(QtWidgets.QWidget):

    def __init__(self, *args, **kwargs):
        super(PackagesPage, self).__init__(*args, **kwargs)


class PreferencePage(QtWidgets.QWidget):

    def __init__(self, *args, **kwargs):
        super(PreferencePage, self).__init__(*args, **kwargs)
