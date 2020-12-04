
import os
from Qt5 import QtCore, QtWidgets
from rez.resolved_context import ResolvedContext
from rez.suite import Suite, SuiteError
from ..common.model import CompleterProxyModel
from ..common.view import Spoiler, SlimTableView
from ..common.view import RequestTextEdit, RequestCompleter
from ..common.delegate import TableViewRowHover
from .model import ToolModel


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
            "name": QtWidgets.QLineEdit(),
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
        layout.setFieldGrowthPolicy(layout.ExpandingFieldsGrow)
        layout.setFormAlignment(QtCore.Qt.AlignTop | QtCore.Qt.AlignLeft)
        layout.setSpacing(0)

        layout = QtWidgets.QVBoxLayout(self)
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
        id_ = str(id(self))

        widgets = {
            "name": QtWidgets.QLineEdit(),
            "request": RequestTextEdit(),
            "resolve": QtWidgets.QPushButton("Resolve"),
            "remove": QtWidgets.QPushButton("Remove"),
            "editor": QtWidgets.QWidget(),
            "prefix": QtWidgets.QLineEdit(),
            "suffix": QtWidgets.QLineEdit(),
            "tools": ToolView(context_id=id_),
        }

        widgets["name"].setPlaceholderText("context name..")
        widgets["request"].setPlaceholderText("requests..")
        widgets["request"].setAcceptRichText(False)
        widgets["request"].setTabChangesFocus(True)

        widgets["prefix"].setPlaceholderText("Tool prefix..")
        widgets["suffix"].setPlaceholderText("Tool suffix..")
        widgets["tools"].setItemDelegate(TableViewRowHover())
        widgets["tools"].setAlternatingRowColors(True)

        widgets["request"].setMaximumHeight(80)
        widgets["tools"].setMaximumHeight(170)

        layout = QtWidgets.QHBoxLayout(widgets["editor"])
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(widgets["prefix"])
        layout.addWidget(widgets["suffix"])

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(widgets["name"])
        layout.addWidget(widgets["request"])
        layout.addWidget(widgets["resolve"])
        layout.addWidget(widgets["remove"])
        layout.addWidget(widgets["editor"])
        layout.addWidget(widgets["tools"])
        layout.setSpacing(2)

        widgets["name"].textChanged.connect(self.on_name_edited)
        widgets["resolve"].clicked.connect(self.on_resolve_clicked)
        widgets["remove"].clicked.connect(self.on_remove_clicked)
        widgets["prefix"].textChanged.connect(self.on_prefix_changed)
        widgets["suffix"].textChanged.connect(self.on_suffix_changed)
        widgets["tools"].alias_changed.connect(self.alias_changed.emit)
        widgets["tools"].hide_changed.connect(self.hide_changed.emit)

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
        name = self._widgets["name"].text()
        if not name:
            print("Name context first.")
            return

        tools_view = self._widgets["tools"]
        request = self._widgets["request"].toPlainText()

        self._data["context"] = None
        tools_view.clear()
        try:
            context = ResolvedContext(request.split())
        except Exception as e:
            print(e)
            return

        context_tools = context.get_tools(request_only=True)
        for pkg_name, (variant, tools) in context_tools.items():
            tools_view.add_tools(tools)

        self._data["context"] = context
        self.resolved.emit(self._id)

    def on_remove_clicked(self):
        self.removed.emit(self._id)

    def on_prefix_changed(self, prefix):
        model = self._widgets["tools"].model()
        model.set_prefix(prefix)
        self.prefix_changed.emit(self._id, prefix)

    def on_suffix_changed(self, suffix):
        model = self._widgets["tools"].model()
        model.set_suffix(suffix)
        self.suffix_changed.emit(self._id, suffix)

    def set_conflicting(self, conflicts):
        model = self._widgets["tools"].model()
        model.set_conflicting(conflicts)

    def clear(self):
        model = self._widgets["tools"].model()
        model.clear()

    def add_tools(self, tools):
        model = self._widgets["tools"].model()
        model.add_items(tools)


class ToolView(SlimTableView):
    alias_changed = QtCore.Signal(str, str, str)
    hide_changed = QtCore.Signal(str, str, bool)

    def __init__(self, context_id, parent=None):
        super(ToolView, self).__init__(parent=parent)
        self.setObjectName("ToolView")
        self._id = context_id

    def dataChanged(self, first, last, roles=None):
        roles = roles or []

        if QtCore.Qt.CheckStateRole in roles:
            data = last.data(ToolModel.ItemRole)
            self.hide_changed.emit(self._id, data["name"], data["hide"])

        if QtCore.Qt.EditRole in roles:
            data = last.data(ToolModel.ItemRole)
            self.alias_changed.emit(self._id, data["name"], data["alias"])

        super(ToolView, self).dataChanged(first, last, roles)
