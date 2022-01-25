
from ._vendor.Qt5 import QtCore, QtWidgets
from ._vendor import qargparse
from . import resources as res
from .widgets import (
    BusyWidget,

    # suite storage
    SuiteBranchWidget,
    SuiteInsightWidget,

    # suite page
    SuiteHeadWidget,
    SuiteDetailsWidget,
    ContextListWidget,
    StackedRequestWidget,
    StackedResolveWidget,
    ContextToolTreeWidget,

    # packages page
    InstalledPackagesWidget,

)

# for type hint
_SigIt = QtCore.SignalInstance


class SuitePage(BusyWidget):
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
        self.setObjectName("SuitePage")

        suite_details = SuiteDetailsWidget()
        suite_head = SuiteHeadWidget(suite_details)

        context_list = ContextListWidget()
        stacked_request = StackedRequestWidget()
        stacked_resolve = StackedResolveWidget()
        tool_stack = ContextToolTreeWidget()
        installed = InstalledPackagesWidget()

        views = QtWidgets.QTabWidget()
        views.addTab(stacked_resolve, "Resolved Details")
        views.addTab(tool_stack, "Tool Stack")
        views.addTab(installed, "Installed Packages")
        views.setTabPosition(views.East)
        views.setDocumentMode(True)

        body_split = QtWidgets.QSplitter()
        body_split.addWidget(context_list)
        body_split.addWidget(stacked_request)
        body_split.addWidget(views)

        body_split.setOrientation(QtCore.Qt.Horizontal)
        body_split.setChildrenCollapsible(False)
        body_split.setContentsMargins(0, 0, 0, 0)
        body_split.setStretchFactor(0, 20)
        body_split.setStretchFactor(1, 40)
        body_split.setStretchFactor(2, 40)

        head_split = QtWidgets.QSplitter()
        head_split.addWidget(suite_details)
        head_split.addWidget(body_split)

        head_split.setOrientation(QtCore.Qt.Vertical)
        head_split.setChildrenCollapsible(False)
        head_split.setStretchFactor(0, 40)
        head_split.setStretchFactor(1, 60)
        head_split.setCollapsible(0, True)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.addWidget(suite_head)
        layout.addWidget(head_split)

        head_split.setObjectName("suitePageHeadSplit")
        body_split.setObjectName("suitePageBodySplit")


class StoragePage(BusyWidget):
    """
     ____________
    /storage view\
    +---------------+-----------------+
    |               |                 |
    |               |                 |
    | Saved Suites  |   Tools View    |
    |               |   (read-only)   |
    |               |                 |
    |               |                 |
    +---------------+-----------------+

    """

    def __init__(self, *args, **kwargs):
        super(StoragePage, self).__init__(*args, **kwargs)
        self.setObjectName("StoragePage")

        storage = SuiteBranchWidget()
        tool_view = SuiteInsightWidget()

        body_split = QtWidgets.QSplitter()
        body_split.addWidget(storage)
        body_split.addWidget(tool_view)

        body_split.setOrientation(QtCore.Qt.Horizontal)
        body_split.setChildrenCollapsible(False)
        body_split.setStretchFactor(0, 50)
        body_split.setStretchFactor(1, 50)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(body_split)


class PreferencePage(QtWidgets.QWidget):
    """Sweet settings
    Changes will be saved and effected immediately.
    """
    changed = QtCore.Signal(str, object)  # type: _SigIt

    def __init__(self, state, *args, **kwargs):
        super(PreferencePage, self).__init__(*args, **kwargs)
        self.setObjectName("Preference")

        doc = QtWidgets.QLabel()
        doc.setObjectName("DocStrings")
        doc.setText(self.__doc__.strip())

        options = qargparse.QArgumentParser([
            qargparse.Separator("Appearance"),

            qargparse.Enum(
                "theme",
                items=res.theme_names(),
                default=0,
                initial=state.retrieve("theme"),
                help="GUI skin. May need to restart Sweet after changed."
            ),

            qargparse.Button(
                "reloadTheme",
                help="Reload current theme."
            ),

            qargparse.Button(
                "resetLayout",
                help="Reset layout back to their defaults."
            ),

            qargparse.Separator("Settings"),

            qargparse.Enum(
                "suiteOpenAs",
                items=["Ask", "Loaded", "Import"],
                default=0,
                initial=state.retrieve("suiteOpenAs")
            ),

        ])

        scroll = QtWidgets.QScrollArea()
        scroll.setWidget(options)
        scroll.setWidgetResizable(True)

        layout = QtWidgets.QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(doc, 0, 0, 1, -1)
        layout.addWidget(scroll, 1, 0, 1, -1)
        layout.setSpacing(4)

        options.changed.connect(self.on_option_changed)

        self._state = state

    def on_option_changed(self, argument):
        name = argument["name"]
        value = argument.read()
        self._state.store(name, value)
        self.changed.emit(name, value)
