
import os
from Qt5 import QtCore, QtWidgets
from rez.resolved_context import ResolvedContext
from rez.suite import Suite, SuiteError
from ..common.model import CompleterProxyModel
from ..common.view import Spoiler, SlimTableView
from ..common.view import RequestTextEdit, RequestCompleter
from ..common.delegate import TableViewRowHover
from .model import ToolsModel


class SphereView(QtWidgets.QWidget):

    def __init__(self, parent=None):
        super(SphereView, self).__init__(parent=parent)
        self.setObjectName("SphereView")

        timers = {
            "toolsUpdate": QtCore.QTimer(self),
        }

        widgets = {
            "icon": QtWidgets.QLabel(),  # TODO: not added yet.. (profile)
            "name": QtWidgets.QLineEdit(),
            "create": QtWidgets.QPushButton("Create"),
            "add": QtWidgets.QPushButton(),

            "scroll": QtWidgets.QScrollArea(),
            "wrap": QtWidgets.QWidget(),
            "context": QtWidgets.QWidget(),
        }
        widgets["add"].setObjectName("SphereAddContextButton")

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
        layout.addWidget(widgets["create"])
        layout.addWidget(widgets["add"])
        layout.addWidget(widgets["scroll"])

        widgets["create"].clicked.connect(self.on_create_clicked)
        widgets["add"].clicked.connect(self.on_add_clicked)
        timers["toolsUpdate"].timeout.connect(self.on_tools_updated)

        self._timers = timers
        self._widgets = widgets
        self._contexts = dict()
        self._data = {
            "suite": Suite(),
            "addedContext": dict(),
            "completerModel": None,
        }

    def reset_tools_update_timer(self):
        self._timers["toolsUpdate"].start(500)

    def set_completer_model(self, model):
        self._data["completerModel"] = model

    def remove_context_by_id(self, id_):
        added = self._data["addedContext"].get(id_)
        if added is not None:
            self._data["suite"].remove_context(added)

    def on_create_clicked(self):
        name = self._widgets["name"].text()
        self._data["suite"].save(os.path.expanduser("~/%s" % name))

    def on_add_clicked(self):
        context_w = ContextView()
        spoiler = Spoiler(title="untitled..")
        spoiler.set_content(context_w)
        spoiler.set_expanded(True)

        model = self._data["completerModel"]
        if model is not None:
            context_w.setup_request_completer(model)

        layout = self._widgets["context"].layout()
        layout.insertRow(0, spoiler)  # new added context has higher priority

        self._contexts[context_w.id()] = context_w

        def on_context_named(text):
            spoiler.set_title(text or "untitled..")
        context_w.named.connect(on_context_named)
        context_w.resolved.connect(self.on_context_resolved)
        context_w.removed.connect(self.on_context_removed)
        context_w.prefix_changed.connect(self.on_context_prefix_changed)
        context_w.suffix_changed.connect(self.on_context_suffix_changed)
        context_w.alias_changed.connect(self.on_context_tool_alias_changed)
        context_w.hide_changed.connect(self.on_context_tool_hide_changed)

    def on_context_resolved(self, id_):
        name, context = self._contexts[id_].get_context()
        self.remove_context_by_id(id_)

        try:
            self._data["suite"].add_context(name, context)
        except SuiteError as err:
            print(err)
        else:
            self._data["addedContext"][id_] = name
            self.reset_tools_update_timer()

    def on_context_removed(self, id_):
        self.remove_context_by_id(id_)
        context_w = self._contexts.pop(id_)
        context_w.deleteLater()
        self.reset_tools_update_timer()

    def on_context_prefix_changed(self, id_, prefix):
        name = self._data["addedContext"][id_]
        suite = self._data["suite"]
        suite.set_context_prefix(name, prefix)
        self.reset_tools_update_timer()

    def on_context_suffix_changed(self, id_, suffix):
        name = self._data["addedContext"][id_]
        suite = self._data["suite"]
        suite.set_context_suffix(name, suffix)
        self.reset_tools_update_timer()

    def on_context_tool_alias_changed(self, id_, tool, alias):
        name = self._data["addedContext"][id_]
        suite = self._data["suite"]
        if alias:
            suite.alias_tool(name, tool, alias)
        else:
            suite.unalias_tool(name, tool)
        self.reset_tools_update_timer()

    def on_context_tool_hide_changed(self, id_, tool, hide):
        name = self._data["addedContext"][id_]
        suite = self._data["suite"]
        if hide:
            suite.hide_tool(name, tool)
        else:
            suite.unhide_tool(name, tool)
        self.reset_tools_update_timer()

    def on_tools_updated(self):
        # TODO: block and unblock gui ?
        # TODO: block suite save if has conflicts
        conflicts = self._data["suite"].get_conflicting_aliases()
        # update tool models
        for context_w in self._contexts.values():
            context_w.set_conflicting(conflicts)


class ContextView(QtWidgets.QWidget):
    named = QtCore.Signal(str)
    resolved = QtCore.Signal(str)
    removed = QtCore.Signal(str)
    prefix_changed = QtCore.Signal(str, str)
    suffix_changed = QtCore.Signal(str, str)
    alias_changed = QtCore.Signal(str, str, str)
    hide_changed = QtCore.Signal(str, str, bool)

    def __init__(self, parent=None):
        super(ContextView, self).__init__(parent=parent)

        widgets = {
            "name": QtWidgets.QLineEdit(),
            "request": RequestTextEdit(),
            "resolve": QtWidgets.QPushButton("Resolve"),
            "remove": QtWidgets.QPushButton("Remove"),
            "tools": ToolsView(),
        }

        widgets["name"].setPlaceholderText("context name..")
        widgets["request"].setPlaceholderText("requests..")
        widgets["request"].setAcceptRichText(False)
        widgets["request"].setTabChangesFocus(True)

        widgets["request"].setMaximumHeight(80)
        widgets["tools"].setMaximumHeight(170)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(widgets["name"])
        layout.addWidget(widgets["request"])
        layout.addWidget(widgets["resolve"])
        layout.addWidget(widgets["remove"])
        layout.addWidget(widgets["tools"])
        layout.setSpacing(2)

        widgets["name"].textChanged.connect(self.on_name_edited)
        widgets["resolve"].clicked.connect(self.on_resolve_clicked)
        widgets["remove"].clicked.connect(self.on_remove_clicked)
        widgets["tools"].prefix_changed.connect(self.on_prefix_changed)
        widgets["tools"].suffix_changed.connect(self.on_suffix_changed)
        widgets["tools"].alias_changed.connect(self.on_alias_changed)
        widgets["tools"].hide_changed.connect(self.on_hide_changed)

        self._widgets = widgets
        self._id = str(id(self))
        self._data = dict()

    def id(self):
        return self._id

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
        self.named.emit(text)

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
        self.prefix_changed.emit(self._id, prefix)

    def on_suffix_changed(self, suffix):
        self.suffix_changed.emit(self._id, suffix)

    def on_alias_changed(self, tool, alias):
        self.alias_changed.emit(self._id, tool, alias)

    def on_hide_changed(self, tool, hide):
        self.hide_changed.emit(self._id, tool, hide)

    def get_context(self):
        name = self._widgets["name"].text()  # check name valid
        context = self._data["context"]
        return name, context

    def save_context(self):
        name, context = self.get_context()
        context.save(os.path.expanduser("~/%s.rxt" % name))

    def set_conflicting(self, conflicts):
        tools_view = self._widgets["tools"]
        tools_view.set_conflicting(conflicts)

    def validate(self):
        pass


class ToolsView(QtWidgets.QWidget):
    prefix_changed = QtCore.Signal(str)
    suffix_changed = QtCore.Signal(str)
    alias_changed = QtCore.Signal(str, str)
    hide_changed = QtCore.Signal(str, bool)

    def __init__(self, parent=None):
        super(ToolsView, self).__init__(parent=parent)
        self.setObjectName("ToolsView")

        widgets = {
            "view": SlimTableView(),
            "editor": QtWidgets.QWidget(),
            "prefix": QtWidgets.QLineEdit(),
            "suffix": QtWidgets.QLineEdit(),
        }
        model = ToolsModel()

        widgets["view"].setItemDelegate(TableViewRowHover())
        widgets["view"].setAlternatingRowColors(True)
        widgets["view"].setModel(model)
        widgets["prefix"].setPlaceholderText("Tool prefix..")
        widgets["suffix"].setPlaceholderText("Tool suffix..")

        layout = QtWidgets.QHBoxLayout(widgets["editor"])
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(widgets["prefix"])
        layout.addWidget(widgets["suffix"])

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(widgets["editor"])
        layout.addWidget(widgets["view"])

        widgets["prefix"].textChanged.connect(self.on_prefix_changed)
        widgets["suffix"].textChanged.connect(self.on_suffix_changed)
        model.alias_changed.connect(self.alias_changed.emit)
        model.hide_changed.connect(self.hide_changed.emit)

        self._widgets = widgets

    def clear(self):
        model = self._widgets["view"].model()
        model.clear()

    def add_tools(self, tools):
        model = self._widgets["view"].model()
        model.add_items(tools)

    def on_prefix_changed(self, text):
        view = self._widgets["view"]
        model = view.model()
        model.set_prefix(text)
        view.viewport().update()
        self.prefix_changed.emit(text)

    def on_suffix_changed(self, text):
        view = self._widgets["view"]
        model = view.model()
        model.set_suffix(text)
        view.viewport().update()
        self.suffix_changed.emit(text)

    def set_conflicting(self, conflicts):
        view = self._widgets["view"]
        model = view.model()
        model.set_conflicting(conflicts)
        view.viewport().update()
