
import os
from Qt5 import QtCore, QtWidgets
from rez.resolved_context import ResolvedContext
from rez.suite import Suite, SuiteError
from ..common.view import Spoiler


class SphereView(QtWidgets.QWidget):

    def __init__(self, parent=None):
        super(SphereView, self).__init__(parent=parent)

        widgets = {
            "icon": QtWidgets.QLabel(),
            "name": QtWidgets.QLineEdit(),
            "create": QtWidgets.QPushButton("Create"),
            "add": QtWidgets.QPushButton("+"),
            "conflict": QtWidgets.QPushButton("Conflict"),

            "scroll": QtWidgets.QScrollArea(),
            "wrap": QtWidgets.QWidget(),
            "context": QtWidgets.QWidget(),
        }

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
        layout.addWidget(widgets["conflict"])
        layout.addWidget(widgets["scroll"])

        widgets["create"].clicked.connect(self.on_create_clicked)
        widgets["add"].clicked.connect(self.on_add_clicked)
        widgets["conflict"].clicked.connect(self.on_conflict_clicked)

        self._widgets = widgets
        self._contexts = dict()
        self._data = {
            "suite": Suite(),
            "addedContext": dict()
        }

    def _remove_context_by_id(self, id_):
        added = self._data["addedContext"].get(id_)
        if added is not None:
            self._data["suite"].remove_context(added)

    def on_create_clicked(self):
        name = self._widgets["name"].text()
        self._data["suite"].save(os.path.expanduser("~/%s" % name))

    def on_add_clicked(self):
        context_w = ContextView()
        spoiler = Spoiler()
        spoiler.set_content(context_w)
        spoiler.set_expanded(True)

        layout = self._widgets["context"].layout()
        layout.insertRow(0, spoiler)  # new added context has higher priority

        self._contexts[context_w.id()] = context_w

        context_w.resolved.connect(self.on_context_resolved)
        context_w.removed.connect(self.on_context_removed)

    def on_conflict_clicked(self):
        print(self._data["suite"].get_conflicting_aliases())

    def on_context_resolved(self, id_):
        name, context = self._contexts[id_].get_context()
        self._remove_context_by_id(id_)

        try:
            self._data["suite"].add_context(name, context)
        except SuiteError as err:
            print(err)
        else:
            self._data["addedContext"][id_] = name

    def on_context_removed(self, id_):
        self._remove_context_by_id(id_)
        context_w = self._contexts.pop(id_)
        context_w.deleteLater()


class ContextView(QtWidgets.QWidget):
    resolved = QtCore.Signal(str)
    removed = QtCore.Signal(str)

    def __init__(self, parent=None):
        super(ContextView, self).__init__(parent=parent)

        widgets = {
            "name": QtWidgets.QLineEdit(),
            "request": QtWidgets.QLineEdit(),
            "resolve": QtWidgets.QPushButton("Resolve"),
            "remove": QtWidgets.QPushButton("Remove"),
            "tools": ToolsView(),
        }

        widgets["name"].setPlaceholderText("context name..")
        widgets["request"].setPlaceholderText("requests..")

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(widgets["name"])
        layout.addWidget(widgets["request"])
        layout.addWidget(widgets["resolve"])
        layout.addWidget(widgets["remove"])
        layout.addWidget(widgets["tools"])

        widgets["resolve"].clicked.connect(self.on_resolve_clicked)
        widgets["remove"].clicked.connect(self.on_remove_clicked)

        # self.setMaximumHeight(200)

        self._widgets = widgets
        self._id = str(id(self))
        self._data = dict()

    def id(self):
        return self._id

    def on_resolve_clicked(self):
        tools_view = self._widgets["tools"]
        request = self._widgets["request"].text()

        self._data["context"] = None
        tools_view.clear()
        try:
            context = ResolvedContext(request.split())
        except Exception as e:
            print(e)
            return

        context_tools = context.get_tools(request_only=True)
        for pkg_name, (variant, tools) in context_tools.items():
            tools_view.add_native_tools(tools)

        self._data["context"] = context
        self.resolved.emit(self._id)

    def on_remove_clicked(self):
        self.removed.emit(self._id)

    def get_context(self):
        name = self._widgets["name"].text()  # check name valid
        context = self._data["context"]
        return name, context

    def save_context(self):
        name, context = self.get_context()
        context.save(os.path.expanduser("~/%s.rxt" % name))

    def validate(self):
        pass


class ToolsView(QtWidgets.QWidget):

    def __init__(self, parent=None):
        super(ToolsView, self).__init__(parent=parent)

        widgets = {
            "editor": QtWidgets.QWidget(),
            "prefix": QtWidgets.QLineEdit(),
            "suffix": QtWidgets.QLineEdit(),
            "views": QtWidgets.QWidget(),
            "native": QtWidgets.QListWidget(),
            "expose": QtWidgets.QListWidget(),
            # double click set alias, selection link with native view
        }
        widgets["prefix"].setPlaceholderText("Tool prefix..")
        widgets["suffix"].setPlaceholderText("Tool suffix..")

        layout = QtWidgets.QVBoxLayout(widgets["editor"])
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(widgets["prefix"])
        layout.addWidget(widgets["suffix"])

        layout = QtWidgets.QHBoxLayout(widgets["views"])
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(widgets["native"])
        layout.addWidget(widgets["expose"])

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(widgets["editor"])
        layout.addWidget(widgets["views"])

        self._widgets = widgets

    def clear(self):
        self._widgets["native"].clear()

    def add_native_tools(self, tools):
        # need to check tool name is valid file name
        self._widgets["native"].addItems(tools)
