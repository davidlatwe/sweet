
from ._vendor.Qt5 import QtCore, QtWidgets
from .widgets import (

    # suite page
    CurrentSuite,
    ContextListWidget,
    StackedResolveView,
    ToolStack,

)


class SuitePage(QtWidgets.QWidget):
    """
     ____________
    /suite editor\
    +---------------------------------+
    | suite name                      |
    |------+-----------+--------------+
    | ctx1 |           |              |
    | ctx2 |  Resolve  |  Tools View  |
    | .... |  Context  |              |
    |      |           |              |
    +------+-----------+--------------+

    """

    def __init__(self, *args, **kwargs):
        super(SuitePage, self).__init__(*args, **kwargs)

        current_suite = CurrentSuite()

        context_list = ContextListWidget()
        stacked_resolve = StackedResolveView()
        tool_stack = ToolStack()

        body_split = QtWidgets.QSplitter()
        body_split.addWidget(context_list)
        body_split.addWidget(stacked_resolve)
        body_split.addWidget(tool_stack)

        body_split.setOrientation(QtCore.Qt.Horizontal)
        body_split.setChildrenCollapsible(False)
        body_split.setStretchFactor(0, 20)
        body_split.setStretchFactor(1, 40)
        body_split.setStretchFactor(2, 40)

        head_split = QtWidgets.QSplitter()
        head_split.addWidget(current_suite)
        head_split.addWidget(body_split)

        head_split.setOrientation(QtCore.Qt.Vertical)
        head_split.setChildrenCollapsible(False)
        head_split.setStretchFactor(0, 40)
        head_split.setStretchFactor(1, 60)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(head_split)

        head_split.setObjectName("suitePageHeadSplit")
        body_split.setObjectName("suitePageBodySplit")


class StoragePage(QtWidgets.QWidget):

    def __init__(self, *args, **kwargs):
        super(StoragePage, self).__init__(*args, **kwargs)


class PackagesPage(QtWidgets.QWidget):

    def __init__(self, *args, **kwargs):
        super(PackagesPage, self).__init__(*args, **kwargs)


class PreferencePage(QtWidgets.QWidget):

    def __init__(self, *args, **kwargs):
        super(PreferencePage, self).__init__(*args, **kwargs)
