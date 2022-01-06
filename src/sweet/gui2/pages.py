
from ._vendor.Qt5 import QtCore, QtWidgets
from .widgets import (
    CurrentSuite,
    ContextStack,
    ToolStack,
    RequestEditor,
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

        request_editor = RequestEditor()  # use StackWidget + ComboBox

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(request_editor)

    def on_context_added(self, ctx):
        pass


class StoragePage(QtWidgets.QWidget):

    def __init__(self, *args, **kwargs):
        super(StoragePage, self).__init__(*args, **kwargs)


class PackagesPage(QtWidgets.QWidget):

    def __init__(self, *args, **kwargs):
        super(PackagesPage, self).__init__(*args, **kwargs)


class PreferencePage(QtWidgets.QWidget):

    def __init__(self, *args, **kwargs):
        super(PreferencePage, self).__init__(*args, **kwargs)
