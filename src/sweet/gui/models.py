
import os
import logging
from datetime import datetime
from itertools import zip_longest

from rez.packages import Variant
from rez.config import config as rezconfig

from .. import util
from ..core import \
    SuiteCtx, SuiteTool, SavedSuite, PkgFamily, PkgVersion, Constants, \
    RollingContext
from . import resources as res
from ._vendor.Qt5 import QtCore, QtGui
from ._vendor import qjsonmodel


log = logging.getLogger("sweet")


class QSingleton(type(QtCore.QObject), type):
    """A metaclass for creating QObject singleton
    https://forum.qt.io/topic/88531/singleton-in-python-with-qobject
    https://bugreports.qt.io/browse/PYSIDE-1434?focusedCommentId=540135#comment-540135
    """
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(QSingleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


def parse_icon(pkg_root, pkg_icon_path, default_icon=None):
    pkg_icon_path = pkg_icon_path or ""
    try:
        fname = pkg_icon_path.format(
            root=pkg_root,
            width=32,
            height=32,
            w=32,
            h=32
        )

    except KeyError:
        fname = ""

    return QtGui.QIcon(fname or default_icon or ":/icons/box-seam.svg")


class _LocationIndicator(QtCore.QObject, metaclass=QSingleton):

    def __init__(self, *args, **kwargs):
        super(_LocationIndicator, self).__init__(*args, **kwargs)
        self._location_icon = [
            QtGui.QIcon(":/icons/person-circle.svg"),  # local
            QtGui.QIcon(":/icons/people-fill.svg"),  # non-local
            QtGui.QIcon(":/icons/people-fill-ok.svg"),  # released
            QtGui.QIcon(":/icons/exclamation-circle-fill.svg")  # not exists
        ]
        self._location_text = [
            "local", "non-local", "released", "not exist"
        ]
        self._non_local = util.normpaths(*rezconfig.nonlocal_packages_path)
        self._release = util.normpath(rezconfig.release_packages_path)

    def compute(self, location):
        norm_location = util.normpath(location)
        is_not_dir = (not os.path.isdir(norm_location)) * 3
        is_released = int(norm_location == self._release) * 2
        is_nonlocal = int(norm_location in self._non_local)
        index = is_not_dir or is_released or is_nonlocal
        location_text = self._location_text[index]
        location_icon = self._location_icon[index]

        return location_text, location_icon


class JsonModel(qjsonmodel.QJsonModel):

    JsonRole = QtCore.Qt.UserRole + 1
    KeyRole = QtCore.Qt.UserRole + 2
    ValueRole = QtCore.Qt.UserRole + 3

    def __init__(self, parent=None):
        super(JsonModel, self).__init__(parent)
        self._headers = ("Key", "Value/[Count]")

    def setData(self, index, value, role):
        # Support copy/paste, but prevent edits
        return False

    def flags(self, index):
        flags = super(JsonModel, self).flags(index)
        return QtCore.Qt.ItemIsEditable | flags

    def data(self, index, role):
        if not index.isValid():
            return None

        item = index.internalPointer()
        parent = item.parent()

        if role in (QtCore.Qt.DisplayRole, QtCore.Qt.EditRole):
            if index.column() == 0:
                if parent.type is list:
                    return f"#{item.key:03} [{parent.childCount()}]"
                return item.key

            if index.column() == 1:
                if item.type is list:
                    return f"[{item.childCount()}]"
                return item.value

        elif role == self.JsonRole:
            return self.json(item)

        elif role == self.KeyRole:
            if parent.type is list:
                return parent.key
            return item.key

        elif role == self.ValueRole:
            return item.value

        return super(JsonModel, self).data(index, role)

    reset = qjsonmodel.QJsonModel.clear


class BaseItemModel(QtGui.QStandardItemModel):
    Headers = []

    def __init__(self, *args, **kwargs):
        super(BaseItemModel, self).__init__(*args, **kwargs)
        self.setColumnCount(len(self.Headers))

    def headerData(self, section, orientation, role=QtCore.Qt.DisplayRole):
        if role == QtCore.Qt.DisplayRole and section < len(self.Headers):
            return self.Headers[section]
        return super(BaseItemModel, self).headerData(
            section, orientation, role)

    def clear(self):
        """Clear model and header

        Removes all items (including header items) from the model and sets
        the number of rows and columns to zero.

        Note: Header view's section resize mode setting will be cleared
            altogether. Consider this action as a full reset.

        """
        super(BaseItemModel, self).clear()  # also clears header items, hence..
        self.setHorizontalHeaderLabels(self.Headers)

    def reset(self):
        """Remove all rows and set row count to zero

        This doesn't touch header.

        """
        self.removeRows(0, self.rowCount())
        self.setRowCount(0)

    def flags(self, index):
        """

        :param index:
        :type index: QtCore.QModelIndex
        :return:
        :rtype: QtCore.Qt.ItemFlags
        """
        return QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable


class ToolTreeModel(BaseItemModel):
    alias_changed = QtCore.Signal(str, str, str)
    hidden_changed = QtCore.Signal(str, str, bool)

    ToolNameRole = QtCore.Qt.UserRole + 10
    ToolEditRole = QtCore.Qt.UserRole + 11
    ToolItemRole = QtCore.Qt.UserRole + 12

    Headers = [
        "Name",  # context name and tool alias
        "From Package",
    ]
    MissingToolsHolder = "<-missing->"

    def __init__(self, editable=True, *args, **kwargs):
        super(ToolTreeModel, self).__init__(*args, **kwargs)
        self._status_icon = {
            Constants.TOOL_VALID: QtGui.QIcon(":/icons/check-ok.svg"),
            Constants.TOOL_HIDDEN: QtGui.QIcon(":/icons/slash-lg.svg"),
            Constants.TOOL_SHADOWED: QtGui.QIcon(":/icons/exclamation-warn.svg"),
            Constants.TOOL_MISSING: QtGui.QIcon(":/icons/x.svg"),
        }
        self._status_tip = {
            Constants.TOOL_VALID: "Can be accessed.",
            Constants.TOOL_HIDDEN: "Is hidden from context.",
            Constants.TOOL_SHADOWED: "Has naming conflict, can't be accessed.",
            Constants.TOOL_MISSING: "Missing from last resolve.",
        }
        self._ctx_items = dict()
        self._editable = editable

    @property
    def editable(self):
        return self._editable

    def reset(self):
        self._ctx_items.clear()
        super(ToolTreeModel, self).reset()

    def get_context_item(self, name):
        """
        :param str name:
        :rtype: QtGui.QStandardItem or None
        """
        return self._ctx_items.get(name)

    def add_context_item(self, name, item):
        """
        :param str name:
        :param QtGui.QStandardItem item:
        :rtype: None
        """
        if name in self._ctx_items:
            log.critical(f"Context item {name!r} already exists in model.")
        self._ctx_items[name] = item

    def pop_context_item(self, name):
        """
        :param str name:
        :rtype: QtGui.QStandardItem or None
        """
        return self._ctx_items.pop(name, None)

    def iter_context_items(self):
        return self._ctx_items.values()

    def update_tools(self, tools):
        """Update tools of one suite
        :param list[SuiteTool] tools:
        """
        indicator = _LocationIndicator()
        missing_grp = self.MissingToolsHolder

        # if any tool missing, ensure the group for them exists, or
        # if no tool missing, ensure the group is removed
        if any(t.status == Constants.TOOL_MISSING for t in tools):
            _item = self.get_context_item(missing_grp)
            if _item is None:
                _item = QtGui.QStandardItem(missing_grp)
                self.add_context_item(missing_grp, _item)
                self.appendRow(_item)
        else:
            _item = self.pop_context_item(missing_grp)
            if _item is not None:
                self.removeRow(_item.row())

        # clear out previous tools from all contexts in current suite
        for ctx_item in self.iter_context_items():
            ctx_item.removeRows(0, ctx_item.rowCount())

        # add new tools
        for tool in sorted(tools, key=lambda t: t.name):
            is_hidden = tool.status == Constants.TOOL_HIDDEN
            is_missing = tool.status == Constants.TOOL_MISSING

            _name = missing_grp if is_missing else tool.ctx_name
            ctx_item = self.get_context_item(_name)
            if ctx_item is None:
                log.critical(f"Context item {_name!r} not exists, {tool.alias} "
                             "not added.")
                continue

            name_item = QtGui.QStandardItem(tool.alias)
            if tool.ambiguous and tool.status == Constants.TOOL_VALID:
                _icon = QtGui.QIcon(":/icons/question-circle.svg")
                _tip = "Same tool vended from multiple packages, unclear " \
                       "which will be used. (depend on $PATH)"
                name_item.setIcon(_icon)
                name_item.setToolTip(_tip)
            else:
                name_item.setIcon(self._status_icon[tool.status])
                name_item.setToolTip(self._status_tip[tool.status])

            name_item.setData(tool, self.ToolItemRole)
            name_item.setData(tool.name, self.ToolNameRole)
            name_item.setData(not is_missing, self.ToolEditRole)
            if not is_missing and self._editable:
                name_item.setData(
                    QtCore.Qt.Unchecked if is_hidden else QtCore.Qt.Checked,
                    QtCore.Qt.CheckStateRole
                )

            _, loc_icon = indicator.compute(tool.location)
            pkg_item = QtGui.QStandardItem(tool.variant.qualified_name)
            pkg_item.setIcon(loc_icon)

            ctx_item.appendRow([name_item, pkg_item])

    def flags(self, index):
        """

        :param index:
        :type index: QtCore.QModelIndex
        :return:
        :rtype: QtCore.Qt.ItemFlags
        """
        if not index.isValid():
            return

        is_tool = bool(index.data(self.ToolItemRole))
        base_flags = QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable

        if self._editable and index.column() == 0 and is_tool:
            if self.data(index, self.ToolEditRole):
                return base_flags | QtCore.Qt.ItemIsUserCheckable

        return base_flags

    def data(self, index, role=QtCore.Qt.DisplayRole):
        """
        :param QtCore.QModelIndex index:
        :param int role:
        :rtype: Any
        """
        if not index.isValid():
            return

        if role == QtCore.Qt.FontRole and index.column() == 0:
            is_tool = bool(index.data(self.ToolItemRole))
            if is_tool and index.data() != index.data(self.ToolNameRole):
                font = QtGui.QFont()
                font.setBold(True)
                return font

        return super(ToolTreeModel, self).data(index, role)

    def setData(self, index, value, role=QtCore.Qt.EditRole):
        """

        :param index:
        :param value:
        :param role:
        :type index: QtCore.QModelIndex
        :type value: Any
        :type role: int
        :return:
        :rtype: bool
        """
        if not (self._editable and index.isValid()):
            return False

        if role == QtCore.Qt.CheckStateRole:
            is_tool = bool(index.data(self.ToolItemRole))
            if index.column() == 0 and is_tool:
                ctx_name = self.data(index.parent(), QtCore.Qt.DisplayRole)
                tool_name = self.data(index, self.ToolNameRole)
                item = self.itemFromIndex(index)
                item.setData(value, QtCore.Qt.CheckStateRole)
                visible = value == QtCore.Qt.Checked
                self.hidden_changed.emit(ctx_name, tool_name, not visible)
                return True

        if role == QtCore.Qt.EditRole:
            is_tool = bool(index.data(self.ToolItemRole))
            if index.column() == 0 and is_tool:
                ctx_name = self.data(index.parent(), QtCore.Qt.DisplayRole)
                tool_name = self.data(index, self.ToolNameRole)
                item = self.itemFromIndex(index)
                item.setData(value, QtCore.Qt.DisplayRole)
                self.alias_changed.emit(ctx_name, tool_name, value)

                return True

        return super(ToolTreeModel, self).setData(index, value, role)


class ContextToolTreeModel(ToolTreeModel):
    require_expanded = QtCore.Signal(list)
    ContextSortRole = QtCore.Qt.UserRole + 20

    def __init__(self, editable=True, *args, **kwargs):
        super(ContextToolTreeModel, self).__init__(editable, *args, **kwargs)
        self._icon_ctx = QtGui.QIcon(":/icons/layers-half.svg")
        self._icon_ctx_f = QtGui.QIcon(":/icons/exclamation-triangle-fill.svg")

    def on_context_resolved(self, name, context):
        icon = self._icon_ctx if context.success else self._icon_ctx_f
        item = self.get_context_item(name)
        if item is None:
            log.critical(f"Context item {name!r} not exists.")
        else:
            item.setIcon(icon)

    def on_context_added(self, ctx):
        """

        :param ctx:
        :type ctx: SuiteCtx
        :return:
        """
        c = self.get_context_item(ctx.name)
        if c is None:
            c = QtGui.QStandardItem(ctx.name)
            c.setIcon(self._icon_ctx)
            c.setData(ctx.priority, self.ContextSortRole)
            self.appendRow(c)
            self.add_context_item(ctx.name, c)
        else:
            # shouldn't happen
            log.critical(f"Context {ctx.name} already exists in model.")

        # for keeping header visible after view resets it's rootIndex.
        c.appendRow([QtGui.QStandardItem() for _ in self.Headers])
        c.removeRow(0)

        self.require_expanded.emit([c.index()])

    def on_context_renamed(self, name, new_name):
        item = self.pop_context_item(name)
        if item is None:
            log.critical(f"Context item {name!r} not exists.(on renamed)")
        else:
            item.setText(new_name)
            self.add_context_item(new_name, item)

    def on_context_dropped(self, name):
        item = self.pop_context_item(name)
        if item is not None:
            self.removeRow(item.row())

    def on_context_reordered(self, new_order):
        for priority, name in enumerate(reversed(new_order)):
            c = self.get_context_item(name)
            if c is None:
                log.critical(f"Context item {name!r} not exists.(on reordered)")
            else:
                c.setData(priority, self.ContextSortRole)

    def on_request_edited(self, name, edited):
        item = self.get_context_item(name)
        if item is None:
            log.critical(f"Context item {name!r} not exists.(on request edited)")
        else:
            font = QtGui.QFont()
            font.setBold(edited)
            font.setItalic(edited)
            item.setFont(font)

    def on_suite_newed(self):
        self.reset()

    def update_tools(self, tools):
        super(ContextToolTreeModel, self).update_tools(tools)
        item = self.get_context_item(self.MissingToolsHolder)
        if item is not None:
            index = item.index()
            # stay on top (with a number that's bigger than all others)
            self.setData(index, value=float("inf"), role=self.ContextSortRole)
            self.require_expanded.emit([index])


class ContextToolTreeModelSingleton(ContextToolTreeModel, metaclass=QSingleton):
    """A singleton model for sharing across tool widgets"""


class ContextToolTreeSortProxyModel(QtCore.QSortFilterProxyModel):

    def __init__(self, *args, **kwargs):
        super(ContextToolTreeSortProxyModel, self).__init__(*args, **kwargs)
        self.setSortRole(ContextToolTreeModel.ContextSortRole)

    def sort(self, column, order=QtCore.Qt.AscendingOrder):
        """

        :param column:
        :param order:
        :type column: int
        :type order: QtCore.Qt.SortOrder
        :return:
        """
        order = QtCore.Qt.DescendingOrder  # fixed
        return super(ContextToolTreeSortProxyModel, self).sort(column, order)


class SuiteCtxToolTreeModel(ToolTreeModel):
    BadSuiteRole = QtCore.Qt.UserRole + 30
    ContextNameRole = QtCore.Qt.UserRole + 31
    ContextSortRole = QtCore.Qt.UserRole + 20

    def __init__(self, editable=True, *args, **kwargs):
        super(SuiteCtxToolTreeModel, self).__init__(editable, *args, **kwargs)
        self._icon_ctx = QtGui.QIcon(":/icons/layers-half.svg")
        self._icon_ctx_f = QtGui.QIcon(":/icons/exclamation-triangle-fill.svg")
        self._suite_items = dict()
        self._suite_namespace = ""

    def reset(self):
        self._suite_items.clear()
        super(SuiteCtxToolTreeModel, self).reset()

    def set_bad_suite(self, item, error):
        item.setData(error, self.BadSuiteRole)

    def is_bad_suite(self, item):
        return item.data(self.BadSuiteRole)

    def suite_key(self, saved_suite):
        return f"{saved_suite.branch}/{saved_suite.name}"

    def find_suite(self, saved_suite):
        """
        :param saved_suite:
        :type saved_suite: SavedSuite
        :return: index of suite item if suite exists in model
        :rtype: QtGui.QStandardItem or None
        """
        key = self.suite_key(saved_suite)
        return self._suite_items.get(key)

    def add_suite(self, saved_suite):
        """
        :param saved_suite:
        :type saved_suite: SavedSuite
        :return: True if added or False if suite already exists in model
        :rtype: bool
        """
        key = self.suite_key(saved_suite)
        exists = key in self._suite_items

        if exists:
            return False
        else:
            root_item = QtGui.QStandardItem(saved_suite.name)
            self.appendRow(root_item)
            self._suite_items[key] = root_item

            c = root_item
            # for keeping header visible after view resets it's rootIndex.
            c.appendRow([QtGui.QStandardItem() for _ in self.Headers])
            c.removeRow(0)

            return True

    def get_context_item(self, name):
        """
        :param str name:
        :rtype: QtGui.QStandardItem or None
        """
        name = f"{self._suite_namespace}/{name}"
        return super(SuiteCtxToolTreeModel, self).get_context_item(name)

    def add_context_item(self, name, item):
        """
        :param str name:
        :param QtGui.QStandardItem item:
        :rtype: None
        """
        name = f"{self._suite_namespace}/{name}"
        super(SuiteCtxToolTreeModel, self).add_context_item(name, item)

    def iter_context_items(self):
        for ctx_name, ctx_item in self._ctx_items.items():
            if ctx_name.startswith(self._suite_namespace + "/"):
                yield ctx_item

    def update_suite_tools(self, saved_suite):
        """Update tools for a suite
        :param saved_suite:
        :type saved_suite: SavedSuite
        :return:
        """
        suite_item = self.find_suite(saved_suite)
        key = self.suite_key(saved_suite)
        self._suite_namespace = key

        for ctx in saved_suite.iter_contexts():
            icon = self._icon_ctx if ctx.context.usable else self._icon_ctx_f
            c = QtGui.QStandardItem(ctx.name)
            c.setIcon(icon)
            c.setData(ctx.name, self.ContextNameRole)
            c.setData(ctx.priority, self.ContextSortRole)
            suite_item.appendRow(c)
            self.add_context_item(ctx.name, c)

        tools = list(saved_suite.iter_saved_tools())
        self.update_tools(tools)
        self._suite_namespace = ""


class ResolvedPackagesModel(BaseItemModel):
    Headers = [
        "Name",
        "Version",
        "Local/Released",
    ]

    PackageRole = QtCore.Qt.UserRole + 10

    def load(self, packages):
        """
        :param packages:
        :type packages: list[Variant]
        :return:
        """
        self.reset()
        indicator = _LocationIndicator()

        for pkg in packages:
            metadata = getattr(pkg, "_data", {})
            pkg_icon = parse_icon(pkg.root, metadata.get("icon"))

            loc_text, loc_icon = indicator.compute(pkg.resource.location)

            name_item = QtGui.QStandardItem(pkg.name)
            name_item.setIcon(pkg_icon)
            name_item.setData(pkg, self.PackageRole)

            version_item = QtGui.QStandardItem(str(pkg.version))

            location_item = QtGui.QStandardItem(loc_text)
            location_item.setIcon(loc_icon)

            self.appendRow([name_item, version_item, location_item])

    def pkg_path_from_index(self, index):
        if not index.isValid():
            return

        item_index = self.index(index.row(), 0)
        package = item_index.data(role=self.PackageRole)
        resource = package.resource

        if resource.key == "filesystem.package":
            return resource.filepath
        elif resource.key == "filesystem.variant":
            return resource.parent.filepath
        elif resource.key == "filesystem.package.combined":
            return resource.parent.filepath
        elif resource.key == "filesystem.variant.combined":
            return resource.parent.parent.filepath


class ResolvedEnvironmentModel(JsonModel):

    def __init__(self, parent=None):
        super(ResolvedEnvironmentModel, self).__init__(parent)
        self._placeholder_color = None
        self._headers = ("Key", "Value", "From")
        self._inspected = dict()
        self._sys_icon = QtGui.QIcon(":/icons/activity.svg")

    def columnCount(self, parent=QtCore.QModelIndex()):
        return 3

    def set_placeholder_color(self, color):
        self._placeholder_color = color

    def _is_path_list(self, value):
        return os.pathsep in value and any(s in value for s in ("/", "\\"))

    def load(self, data):
        # Convert PATH-like environment variables to lists
        # for improved viewing experience
        for key, value in data.copy().items():
            if self._is_path_list(value):
                value = value.split(os.pathsep)
            data[key] = value

        super(ResolvedEnvironmentModel, self).load(data)

    def note(self, inspection):
        """
        :param inspection:
        :type inspection: list[tuple[Variant or str or None, str, str]]
        """
        for scope, key, value in inspection:
            if self._is_path_list(str(value)):
                for path in value.split(os.pathsep):
                    self._inspected[f"{key}/{path}"] = scope
            else:
                self._inspected[f"{key}/{value}"] = scope

    def data(self, index, role=QtCore.Qt.DisplayRole):
        if not index.isValid():
            return None

        item = index.internalPointer()
        parent = item.parent()

        if role == QtCore.Qt.DisplayRole:
            if index.column() == 2:
                if parent.type is list:
                    scope = self._inspected.get(f"{parent.key}/{item.value}")
                else:
                    scope = self._inspected.get(f"{item.key}/{item.value}")

                if isinstance(scope, Variant):
                    return scope.qualified_name
                elif isinstance(scope, str):
                    return f"({scope})"
                return None

        if role == QtCore.Qt.DecorationRole:
            if index.column() == 2:
                if parent.type is list:
                    scope = self._inspected.get(f"{parent.key}/{item.value}")
                else:
                    scope = self._inspected.get(f"{item.key}/{item.value}")

                if isinstance(scope, Variant):
                    metadata = getattr(scope, "_data", {})
                    return parse_icon(scope.root, metadata.get("icon"))
                elif isinstance(scope, str):
                    return self._sys_icon
                return None

        if role == QtCore.Qt.ForegroundRole:
            column = index.column()
            if (column == 1 and item.type is list) \
                    or (column == 0 and parent.type is list):
                return self._placeholder_color

        if role == QtCore.Qt.TextAlignmentRole:
            column = index.column()
            if column == 0 and parent.type is list:
                return QtCore.Qt.AlignRight

        return super(ResolvedEnvironmentModel, self).data(index, role)

    def flags(self, index):
        """
        :param QtCore.QModelIndex index:
        :rtype: QtCore.Qt.ItemFlags
        """
        if not index.isValid():
            return

        base_flags = QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable

        if index.column() == 0:
            item = index.internalPointer()
            if item.parent().type is not list:
                return base_flags | QtCore.Qt.ItemIsEditable

        if index.column() == 1:
            item = index.internalPointer()
            if item.type is not list:
                return base_flags | QtCore.Qt.ItemIsEditable

        return base_flags


class ResolvedEnvironmentProxyModel(QtCore.QSortFilterProxyModel):

    def __init__(self, *args, **kwargs):
        super(ResolvedEnvironmentProxyModel, self).__init__(*args, **kwargs)
        self.setFilterCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self.setSortCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self.setRecursiveFilteringEnabled(True)
        self._inverse = False

    def filter_by_key(self):
        self.setFilterRole(JsonModel.KeyRole)
        self.invalidateFilter()

    def filter_by_value(self):
        self.setFilterRole(JsonModel.ValueRole)
        self.invalidateFilter()

    def inverse_filter(self, value):
        self._inverse = bool(value)
        self.invalidateFilter()

    def filterAcceptsRow(self,
                         source_row: int,
                         source_parent: QtCore.QModelIndex) -> bool:
        accept = super(ResolvedEnvironmentProxyModel,
                       self).filterAcceptsRow(source_row, source_parent)
        if self._inverse:
            return not accept
        return accept


class _PendingContext:
    __getattr__ = (lambda self, k: "")
    success = usable = True
    package_paths = resolved_packages = resolved_ephemerals \
        = _package_requests = implicit_packages = package_filter \
        = package_orderers = []


class ContextDataModel(BaseItemModel):
    FieldNameRole = QtCore.Qt.UserRole + 10
    PlaceholderRole = QtCore.Qt.UserRole + 11
    Headers = [
        "Field",
        "Value",
    ]

    def __init__(self, *args, **kwargs):
        super(ContextDataModel, self).__init__(*args, **kwargs)
        self._show_attr = False  # don't reset this, for sticking toggle state
        self._placeholder_color = None
        self._context = None  # type: RollingContext or None
        self._in_diff = None  # type: RollingContext or None

    def reset(self):
        super(ContextDataModel, self).reset()
        self._context = None
        self._in_diff = None

    def pending(self):
        self.load(_PendingContext())  # noqa

    def load(self, context: RollingContext, diff=False):
        if diff and self._in_diff:
            log.critical("Context model already in diff mode.")
            return

        if diff:
            self._in_diff = context
        else:
            self.reset()
            self._context = context

        self.read("suite_context_name", "Context Name", "not saved/loaded")
        self.read("status", "Context Status", "no data")
        if not context.success:
            self.read("failure_description", "Why Failed")
        if not context.usable:
            self.read("err_on_get_tools", "Why Not Usable")
        self.read("created", "Resolved Date")
        self.read("requested_timestamp", "Ignore Packages After", "no timestamp set")
        self.read("package_paths")

        self.read("_package_requests", "Requests")
        self.read("resolved_packages")
        self.read("resolved_ephemerals")
        self.read("implicit_packages")
        self.read("package_filter")
        self.read("package_orderers")

        self.read("load_time")
        self.read("solve_time")
        self.read("num_loaded_packages", "Packages Queried")
        self.read("caching", "MemCache Enabled")
        self.read("from_cache", "Is MemCached Resolve")
        self.read("building", "Is Building")
        self.read("package_caching", "Cached Package Allowed")
        self.read("append_sys_path")

        self.read("parent_suite_path", "Suite Path")
        self.read("load_path", ".RXT Path")

        self.read("rez_version")
        self.read("rez_path")
        self.read("os", "OS")
        self.read("arch")
        self.read("platform")
        self.read("host")
        self.read("user")

    def find(self, field):
        for row in range(self.rowCount()):
            index = self.index(row, 0)
            if field == index.data(self.FieldNameRole):
                return index

    def read(self, field, pretty=None, placeholder=None):
        placeholder = placeholder or ""
        pretty = pretty or " ".join(w.capitalize() for w in field.split("_"))
        context = self._in_diff or self._context  # type: RollingContext
        assert context is not None

        # value
        icon = None
        value = getattr(context, field) or ""

        if self._in_diff and value == getattr(self._context, field):
            return  # same value, no need to diff

        if field in ("created", "requested_timestamp"):
            if value:
                dt = datetime.fromtimestamp(value)
                value = dt.strftime("%b %d %Y %H:%M:%S")
            else:
                value = ""

        elif field == "status" and value != "":
            value = "broken" if context.broken else value.name
            value += "" if context.usable else " (but not usable)"

        elif field == "load_time" and value != "":
            value = f"{value:.02} secs"

        elif field == "solve_time" and value != "":
            actual_solve_time = value - context.load_time
            value = f"{actual_solve_time:.02} secs"

        elif field == "package_paths":
            indicator = _LocationIndicator()
            icon = [indicator.compute(v)[1] for v in value]

        elif field == "resolved_packages":
            indicator = _LocationIndicator()
            icon = [indicator.compute(pkg.resource.location)[1] for pkg in value]
            value = [pkg.qualified_name for pkg in value]

        elif field == "err_on_get_tools":
            field = ""

        # add row(s)

        if isinstance(value, list):
            icon = icon or [res.icon("dot.svg")] * len(value)
            value = [str(v) for v in value]

            field_item = QtGui.QStandardItem(pretty)
            field_item.setData(field, self.FieldNameRole)

            value_item = QtGui.QStandardItem()
            value_item.setText("" if value else placeholder or "")
            value_item.setData(not value, self.PlaceholderRole)
            value_item.setIcon(res.icon("plus.svg"))

            self.appendRow([field_item, value_item])

            for i, (value, ico_) in enumerate(zip_longest(value, icon)):
                field_item = QtGui.QStandardItem(f"#{i}")
                field_item.setData(True, self.PlaceholderRole)

                value_item = QtGui.QStandardItem(value)
                value_item.setIcon(ico_) if ico_ else None

                self.appendRow([field_item, value_item])

        else:
            if isinstance(value, bool):
                icon = icon or res.icon("check-ok.svg" if value else "slash-lg.svg")
                value = "yes" if value else "no"
            else:
                icon = icon or res.icon("dash.svg")
                value = str(value or "")

            field_item = QtGui.QStandardItem(pretty)
            field_item.setData(field, self.FieldNameRole)

            value_item = QtGui.QStandardItem()
            value_item.setText(value or placeholder)
            value_item.setData(not value, self.PlaceholderRole)
            value_item.setIcon(icon)

            self.appendRow([field_item, value_item])

    @QtCore.Slot(bool)  # noqa
    def on_pretty_shown(self, show_pretty: bool):
        self._show_attr = not show_pretty

    def set_placeholder_color(self, color):
        self._placeholder_color = color

    def setData(self, index, value, role=QtCore.Qt.EditRole):
        # for viewing/copying context data (especially when the value is a
        # long path), item-editable flag is given. We re-implementing this
        # method is just to ensure the value unchanged after edit-mode ended.
        #
        self.dataChanged.emit(index, index, 1)  # trigger column width update
        return True

    def data(self, index, role=QtCore.Qt.DisplayRole):
        if not index.isValid():
            return

        if role == QtCore.Qt.DisplayRole or role == QtCore.Qt.EditRole:
            column = index.column()
            if column == 0 and self._show_attr:
                return index.data(self.FieldNameRole)
            if column == 1 and role == QtCore.Qt.EditRole:
                return "" if index.data(self.PlaceholderRole) \
                    else super(ContextDataModel, self).data(index, role)

        if role == QtCore.Qt.ForegroundRole:
            if index.data(self.PlaceholderRole):
                return self._placeholder_color

        if role == QtCore.Qt.FontRole:
            column = index.column()
            if column == 0 and self._show_attr:
                return QtGui.QFont("JetBrains Mono")

        if role == QtCore.Qt.TextAlignmentRole:
            column = index.column()
            if column == 0:
                return QtCore.Qt.AlignRight

        return super(ContextDataModel, self).data(index, role)

    def flags(self, index):
        """
        :param QtCore.QModelIndex index:
        :rtype: QtCore.Qt.ItemFlags
        """
        if not index.isValid():
            return
        column = index.column()

        base_flags = QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable
        if (column == 0 and self._show_attr) or column == 1:
            return base_flags | QtCore.Qt.ItemIsEditable
        return base_flags


class InstalledPackagesModel(BaseItemModel, metaclass=QSingleton):
    """
    Note: This is a singleton.
    """
    family_updated = QtCore.Signal()

    FilterRole = QtCore.Qt.UserRole + 10
    CompletionRole = QtCore.Qt.UserRole + 11
    PackageObjectRole = QtCore.Qt.UserRole + 12

    Headers = [
        "Name",
        "Date",
    ]

    def __init__(self, *args, **kwargs):
        super(InstalledPackagesModel, self).__init__(*args, **kwargs)
        self._initials = dict()  # type: dict[str, QtGui.QStandardItem]
        self._families = dict()  # type: dict[str, QtGui.QStandardItem]

    def reset(self):
        self._initials.clear()
        self._families.clear()
        super(InstalledPackagesModel, self).reset()

    def initials(self):
        return sorted(self._initials.keys())

    def first_item_in_initial(self, letter):
        return self._initials.get(letter)

    def add_families(self, families):
        """
        :param families:
        :type families: list[PkgFamily]
        :return:
        """
        _families = self._families
        for family in families:
            name = family.name
            if name in _families:
                name_item = _families[family.name]
                name_item.data(self.PackageObjectRole).append(family)

            else:
                name_item = QtGui.QStandardItem(name)
                _families[name] = name_item

                name_item.setData([family], self.PackageObjectRole)
                name_item.setData(name, self.CompletionRole)

                date_item = QtGui.QStandardItem()  # for latest version

                self.appendRow([name_item, date_item])

                initial = name[0].upper()
                if initial not in self._initials:
                    self._initials[initial] = name_item

        self.family_updated.emit()

    def add_versions(self, versions):
        """

        :param versions:
        :type versions: list[PkgVersion]
        :return:
        """
        if not versions:
            return
        _sample = versions[0]
        family = self._families.get(_sample.name)
        if not family:
            return

        _versions = dict()  # type: dict[str, QtGui.QStandardItem]
        _times = set()
        for pkg in sorted(versions, key=lambda v: v.version):
            qualified = pkg.qualified

            if qualified in _versions:
                name_item = _versions[qualified]
                name_item.data(self.PackageObjectRole).append(pkg)

            else:
                keys = "%s,%s" % (qualified, ",".join(pkg.tools))
                _times.add(pkg.timestamp or -1)

                name_item = QtGui.QStandardItem(qualified)
                _versions[qualified] = name_item

                name_item.setData([pkg], self.PackageObjectRole)
                name_item.setData(keys, self.FilterRole)
                name_item.setData(str(pkg.version), self.CompletionRole)

                date_item = QtGui.QStandardItem()
                date_item.setData(pkg.timestamp, QtCore.Qt.DisplayRole)

                family.appendRow([name_item, date_item])

        latest = next(iter(sorted(_times, reverse=True)), -1)
        if latest >= 0:
            date_item = self.itemFromIndex(self.index(family.row(), 1))
            date_item.setData(latest, QtCore.Qt.DisplayRole)

    def data(self, index, role=QtCore.Qt.DisplayRole):
        """

        :param index:
        :param role:
        :type index: QtCore.QModelIndex
        :type role: int
        :return:
        :rtype: Any
        """
        if not index.isValid():
            return

        if role == self.PackageObjectRole:
            item = self.itemFromIndex(self.index(index.row(), 0))
            return item.data(self.PackageObjectRole)

        return super(InstalledPackagesModel, self).data(index, role)


class InstalledPackagesProxyModel(QtCore.QSortFilterProxyModel):

    def __init__(self, *args, **kwargs):
        super(InstalledPackagesProxyModel, self).__init__(*args, **kwargs)
        self.setFilterCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self.setSortCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self.setFilterRole(InstalledPackagesModel.FilterRole)
        self.setRecursiveFilteringEnabled(True)


class SuiteStorageModel(BaseItemModel):
    SavedSuiteRole = QtCore.Qt.UserRole + 10
    ViewedRole = QtCore.Qt.UserRole + 11
    Headers = [
        "Name",
    ]

    def __init__(self, *args, **kwargs):
        super(SuiteStorageModel, self).__init__(*args, **kwargs)
        self._icons = {
            "branch": QtGui.QIcon(":/icons/server.svg"),
            "suite": QtGui.QIcon(":/icons/stack.svg"),
        }

    def ensure_branch_item(self, branch):
        branch_item = self.find_branch(branch)

        if branch_item is None:
            branch_item = QtGui.QStandardItem(branch)
            branch_item.setIcon(self._icons["branch"])
            self.appendRow(branch_item)

        return branch_item

    def add_saved_suites(self, suites):
        """

        :param suites:
        :type suites: list[SavedSuite]
        :return:
        """
        branches = dict()
        for suite in suites:
            if suite.branch not in branches:
                branches[suite.branch] = self.ensure_branch_item(suite.branch)

            suite_item = QtGui.QStandardItem(suite.name)
            suite_item.setIcon(self._icons["suite"])
            suite_item.setData(suite, self.SavedSuiteRole)
            suite_item.setData(False, self.ViewedRole)
            branches[suite.branch].appendRow(suite_item)

    def add_one_saved_suite(self, suite):
        suite_item = self.find_suite(suite)
        if suite_item is not None:
            return  # should be a loaded suite and just being saved over

        suite_item = QtGui.QStandardItem(suite.name)
        suite_item.setIcon(self._icons["suite"])
        suite_item.setData(suite, self.SavedSuiteRole)
        suite_item.setData(False, self.ViewedRole)
        self.ensure_branch_item(suite.branch).appendRow(suite_item)

    def remove_one_saved_suite(self, suite):
        suite_item = self.find_suite(suite)
        if suite_item is None:
            log.critical(f"{suite.branch}/{suite.name} not found in model.")
            return
        index = suite_item.index()
        self.removeRow(index.row(), index.parent())

    def find_branch(self, branch):
        """
        :param str branch:
        :return:
        :rtype: QtGui.QStandardItem or None
        """
        return next(iter(self.findItems(branch)), None)

    def find_suite(self, suite):
        """
        :param SavedSuite suite:
        :return:
        :rtype: QtGui.QStandardItem or None
        """
        branch = self.find_branch(suite.branch)
        if branch is None:
            return

        parent = branch.index()
        for row in range(branch.rowCount()):
            index = self.index(row, 0, parent)
            if index.data() == suite.name:
                return self.itemFromIndex(index)

    def mark_as_viewed(self, suite):
        suite_item = self.find_suite(suite)

        if suite_item is None:
            branch_dummy = not (suite.branch and suite.name)
            if not branch_dummy:
                log.critical(f"Suite {suite.branch}/{suite.name} not in model.")
            return

        suite_item.setData(True, self.ViewedRole)


class CompleterProxyModel(QtCore.QSortFilterProxyModel):
    def data(self, index, role=QtCore.Qt.DisplayRole):
        if role == QtCore.Qt.CheckStateRole:  # disable checkbox
            return
        return super(CompleterProxyModel, self).data(index, role)
