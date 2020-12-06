
from ..vendor.Qt5 import QtCore, QtWidgets
from ..common.model import CompleterProxyModel
from ..common.view import SlimTableView
from ..common.view import RequestTextEdit, RequestCompleter
from ..common.delegate import TableViewRowHover
from .model import ToolModel
from .. import resources as res


class SphereAddContextButton(QtWidgets.QPushButton):
    def __init__(self, parent=None):
        super(SphereAddContextButton, self).__init__(parent=parent)
        self.setObjectName("SphereAddContextButton")


class SphereView(QtWidgets.QWidget):

    suite_named = QtCore.Signal(str)
    suite_saved = QtCore.Signal()
    context_drafted = QtCore.Signal()

    def __init__(self, parent=None):
        super(SphereView, self).__init__(parent=parent)
        self.setObjectName("SphereView")

        widgets = {
            "icon": QtWidgets.QLabel(),  # TODO: not added yet.. (profile)
            "name": QtWidgets.QLineEdit(),  # TODO: add name validator
            "save": QtWidgets.QPushButton("Save Suite"),
            "draft": SphereAddContextButton(),

            "scroll": QtWidgets.QScrollArea(),
            "wrap": QtWidgets.QWidget(),
            "context": QtWidgets.QWidget(),
        }

        widgets["name"].setPlaceholderText("Suite name..")
        widgets["scroll"].setWidget(widgets["wrap"])
        widgets["scroll"].setWidgetResizable(True)

        layout = QtWidgets.QVBoxLayout(widgets["wrap"])
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(widgets["context"])
        layout.addStretch(20)  # so context views can shrink back to top
        layout.setSpacing(0)

        layout = QtWidgets.QFormLayout(widgets["context"])
        layout.setContentsMargins(6, 8, 6, 4)
        layout.setFieldGrowthPolicy(layout.ExpandingFieldsGrow)
        layout.setFormAlignment(QtCore.Qt.AlignTop | QtCore.Qt.AlignLeft)
        layout.setSpacing(0)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(widgets["name"])
        layout.addWidget(widgets["save"])
        layout.addWidget(widgets["draft"])
        layout.addWidget(widgets["scroll"])

        widgets["name"].textChanged.connect(self.suite_named.emit)
        widgets["save"].clicked.connect(self.suite_saved.emit)
        widgets["draft"].clicked.connect(self.context_drafted.emit)

        self._widgets = widgets
        self._contexts = dict()

    def add_context(self, widget, id_):
        # newly added context has higher priority, hence row=0
        layout = self._widgets["context"].layout()
        layout.insertRow(0, widget)
        self._contexts[id_] = widget

    def remove_context(self, id_):
        widget = self._contexts.pop(id_)
        widget.deleteLater()


class ContextView(QtWidgets.QWidget):

    named = QtCore.Signal(str, str)
    requested = QtCore.Signal(str, list)
    removed = QtCore.Signal(str)
    prefix_changed = QtCore.Signal(str, str)
    suffix_changed = QtCore.Signal(str, str)
    alias_changed = QtCore.Signal(str, str, str)
    hide_changed = QtCore.Signal(str, str, bool)

    def __init__(self, parent=None):
        super(ContextView, self).__init__(parent=parent)
        self.setObjectName("ContextView")
        id_ = str(id(self))

        panels = {
            "body": QtWidgets.QWidget(),
            "side": QtWidgets.QWidget(),
        }
        panels["side"].setObjectName("ContextOperationBar")

        widgets = {
            # TODO:
            #  * add name validator
            #  * load context if input name is filepath ends with .rxt
            "name": QtWidgets.QLineEdit(),
            "request": RequestTextEdit(),
            "prefix": QtWidgets.QLineEdit(),
            "suffix": QtWidgets.QLineEdit(),
            "tools": ToolView(context_id=id_),
            # context operation btn
            "bump": QtWidgets.QPushButton(),
            "parse": QtWidgets.QPushButton(),
            "resolve": QtWidgets.QPushButton(),
            "timestamp": QtWidgets.QPushButton(),
            "filter": QtWidgets.QPushButton(),
            "building": QtWidgets.QPushButton(),
            "detail": QtWidgets.QPushButton(),
            "remove": QtWidgets.QPushButton(),
        }
        widgets["bump"].setObjectName("ContextBumpOpBtn")
        widgets["parse"].setObjectName("ContextParseRequestOpBtn")
        widgets["resolve"].setObjectName("ContextResolveOpBtn")
        widgets["timestamp"].setObjectName("ContextTimestampOpBtn")
        widgets["filter"].setObjectName("ContextFilterOpBtn")
        widgets["building"].setObjectName("ContextBuildingOpBtn")
        widgets["detail"].setObjectName("ContextDetailOpBtn")
        widgets["remove"].setObjectName("ContextRemoveOpBtn")

        widgets["name"].setPlaceholderText("context name..")
        widgets["request"].setPlaceholderText("requests..")
        widgets["request"].setAcceptRichText(False)
        widgets["request"].setTabChangesFocus(True)

        widgets["prefix"].setPlaceholderText("tool prefix..")
        widgets["suffix"].setPlaceholderText("tool suffix..")
        widgets["tools"].setItemDelegate(TableViewRowHover())
        widgets["tools"].setAlternatingRowColors(True)

        widgets["request"].setMaximumHeight(60)
        widgets["tools"].setMaximumHeight(140)

        layout = QtWidgets.QGridLayout(panels["body"])
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(widgets["name"], 0, 0, 1, -1)
        layout.addWidget(widgets["prefix"], 1, 0, 1, 1)
        layout.addWidget(widgets["suffix"], 1, 1, 1, 1)
        layout.addWidget(widgets["request"], 2, 0, 1, -1)
        layout.addWidget(widgets["tools"], 3, 0, 1, -1)
        layout.setSpacing(2)

        layout = QtWidgets.QGridLayout(panels["side"])
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(widgets["bump"], 0, 0)  # TODO: bump context
        layout.addItem(QtWidgets.QSpacerItem(1, 12), 1, 0)
        layout.addWidget(widgets["parse"], 2, 0)  # TODO: parse from search
        layout.addWidget(widgets["resolve"], 3, 0)
        layout.addWidget(widgets["timestamp"], 4, 0)  # TODO: pkg timestamp
        layout.addWidget(widgets["filter"], 5, 0)  # TODO: pkg filter
        layout.addWidget(widgets["building"], 6, 0)  # TODO: pkg building env
        layout.addWidget(widgets["detail"], 7, 0)  # TODO: view resolved info
        layout.addWidget(widgets["remove"], 8, 0, QtCore.Qt.AlignBottom)
        layout.setSpacing(6)

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(panels["side"])
        layout.addWidget(panels["body"], stretch=True)
        layout.setSpacing(6)

        widgets["name"].textChanged.connect(self.on_name_edited)
        widgets["resolve"].clicked.connect(self.on_resolve_clicked)
        widgets["remove"].clicked.connect(self.on_remove_clicked)
        widgets["prefix"].textChanged.connect(self.on_prefix_changed)
        widgets["suffix"].textChanged.connect(self.on_suffix_changed)
        widgets["tools"].alias_changed.connect(self.alias_changed.emit)
        widgets["tools"].hide_changed.connect(self.hide_changed.emit)

        self._panels = panels
        self._widgets = widgets
        self._id = id_
        self._data = dict()

    def id(self):
        return self._id

    def setup_tool_view(self, model):
        self._widgets["tools"].setModel(model)

    def setup_request_completer(self, model):
        requester = self._widgets["request"]
        completer = RequestCompleter(requester)
        completer.setModelSorting(completer.CaseInsensitivelySortedModel)
        completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
        completer.setWrapAround(False)

        proxy = CompleterProxyModel()
        proxy.setSourceModel(model)
        completer.setCompletionColumn(model.CompletionColumn)
        completer.setCompletionRole(model.CompletionRole)
        completer.setModel(proxy)

        requester.setCompleter(completer)
        self._widgets["completer"] = completer

    def on_name_edited(self, text):
        self.named.emit(self._id, text)

    def on_resolve_clicked(self):
        request = self._widgets["request"].toPlainText()
        self.requested.emit(self._id, request.split())

    def on_remove_clicked(self):
        self.removed.emit(self._id)

    def on_prefix_changed(self, prefix):
        self.prefix_changed.emit(self._id, prefix)

    def on_suffix_changed(self, suffix):
        self.suffix_changed.emit(self._id, suffix)


class ToolView(SlimTableView):
    alias_changed = QtCore.Signal(str, str, str)
    hide_changed = QtCore.Signal(str, str, bool)

    def __init__(self, context_id, parent=None):
        super(ToolView, self).__init__(parent=parent)
        self.setObjectName("ToolView")
        self._id = context_id

        header = self.verticalHeader()
        header.setDefaultSectionSize(24)  # fixed table row height

    def dataChanged(self, first, last, roles=None):
        roles = roles or []

        if QtCore.Qt.CheckStateRole in roles:
            data = last.data(ToolModel.ItemRole)
            self.hide_changed.emit(self._id, data["name"], data["hide"])

        if QtCore.Qt.EditRole in roles:
            data = last.data(ToolModel.ItemRole)
            self.alias_changed.emit(self._id, data["name"], data["alias"])

        super(ToolView, self).dataChanged(first, last, roles)
