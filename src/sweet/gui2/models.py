
import os
from .. import constants
from ..core import SuiteCtx, SuiteTool, SavedSuite
from ._vendor.Qt5 import QtCore, QtGui
from ._vendor import qjsonmodel
from . import resources as res


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


class JsonModel(qjsonmodel.QJsonModel):

    JsonRole = QtCore.Qt.UserRole + 1

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

        if role in (QtCore.Qt.DisplayRole, QtCore.Qt.EditRole):
            if index.column() == 0:
                return item.key

            if index.column() == 1:
                return item.value

        if role == self.JsonRole:
            return self.json(item)

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
        super(BaseItemModel, self).clear()  # also clears header items, hence..
        self.setHorizontalHeaderLabels(self.Headers)


class ToolStackModel(BaseItemModel, metaclass=QSingleton):
    alias_changed = QtCore.Signal(str, str, str)
    hidden_changed = QtCore.Signal(str, str, bool)

    ToolNameRole = QtCore.Qt.UserRole + 10
    ContextSortRole = QtCore.Qt.UserRole + 11
    Headers = [
        "Name",  # context name and tool alias
        "Status",
        "From Package",
    ]

    def __init__(self, *args, **kwargs):
        super(ToolStackModel, self).__init__(*args, **kwargs)
        self._status_icon = {
            constants.TOOL_VALID: res.icon("images", "check-ok"),
            constants.TOOL_HIDDEN: res.icon("images", "slash-lg"),
            constants.TOOL_SHADOWED: res.icon("images", "exclamation-warn"),
            constants.TOOL_MISSING: res.icon("images", "x"),
        }
        self._status_tip = {
            constants.TOOL_VALID: "Can be accessed.",
            constants.TOOL_HIDDEN: "Is hidden from context.",
            constants.TOOL_SHADOWED: "Has naming conflict, can't be accessed.",
            constants.TOOL_MISSING: "Missing from last resolve.",
        }
        self._context_items = dict()

    def on_context_added(self, ctx):
        """

        :param ctx:
        :type ctx: SuiteCtx
        :return:
        """
        c = QtGui.QStandardItem(ctx.name)
        c.setData(ctx.priority, self.ContextSortRole)
        self.appendRow(c)
        self._context_items[ctx.name] = c

        # for keeping header visible after view resets it's rootIndex.
        c.appendRow([QtGui.QStandardItem() for _ in range(len(self.Headers))])
        c.removeRow(0)

    def on_context_renamed(self, name, new_name):
        item = self._context_items.pop(name)
        item.setText(new_name)
        self._context_items[new_name] = item

    def on_context_dropped(self, name):
        item = self._context_items.pop(name)
        self.removeRow(item.row())

    def on_context_reordered(self, new_order):
        for priority, name in enumerate(reversed(new_order)):
            c = self._context_items[name]
            c.setData(priority, self.ContextSortRole)

    def update_tools(self, tools):
        """

        :param tools:
        :type tools: list[SuiteTool]
        :return:
        """
        for context in self._context_items.values():
            context.removeRows(0, context.rowCount())

        for tool in sorted(tools, key=lambda t: t.name):
            context_item = self._context_items[tool.ctx_name]
            is_hidden = tool.status == constants.TOOL_HIDDEN

            name_item = QtGui.QStandardItem(tool.alias)
            name_item.setData(tool.name, self.ToolNameRole)
            name_item.setData(
                QtCore.Qt.Unchecked if is_hidden else QtCore.Qt.Checked,
                QtCore.Qt.CheckStateRole
            )
            status_item = QtGui.QStandardItem()
            status_item.setIcon(self._status_icon[tool.status])
            status_item.setToolTip(self._status_tip[tool.status])

            pkg_item = QtGui.QStandardItem(tool.variant.qualified_name)

            context_item.appendRow([name_item, status_item, pkg_item])

    def find_context_index(self, name):
        if name in self._context_items:
            return self._context_items[name].index()

    def flags(self, index):
        """

        :param index:
        :type index: QtCore.QModelIndex
        :return:
        :rtype: QtCore.Qt.ItemFlags
        """
        if not index.isValid():
            return

        is_context = index.parent() == self.invisibleRootItem().index()
        base_flags = QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable

        if index.column() == 0 and not is_context:
            return (
                base_flags
                | QtCore.Qt.ItemIsEditable
                | QtCore.Qt.ItemIsUserCheckable
            )
        else:
            return base_flags

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
        if not index.isValid():
            return False

        if role == QtCore.Qt.CheckStateRole:
            is_context = index.parent() == self.invisibleRootItem().index()
            if index.column() == 0 and not is_context:
                ctx_name = self.data(index.parent(), QtCore.Qt.DisplayRole)
                tool_name = self.data(index, self.ToolNameRole)
                item = self.itemFromIndex(index)
                item.setData(value, QtCore.Qt.CheckStateRole)
                visible = value == QtCore.Qt.Checked
                self.hidden_changed.emit(ctx_name, tool_name, not visible)
                return True

        if role == QtCore.Qt.EditRole:
            is_context = index.parent() == self.invisibleRootItem().index()
            if index.column() == 0 and not is_context:
                if value:
                    ctx_name = self.data(index.parent(), QtCore.Qt.DisplayRole)
                    tool_name = self.data(index, self.ToolNameRole)
                    item = self.itemFromIndex(index)
                    item.setData(value, QtCore.Qt.DisplayRole)
                    self.alias_changed.emit(ctx_name, tool_name, value)
                return True

        return super(ToolStackModel, self).setData(index, value, role)


class ToolStackSortProxyModel(QtCore.QSortFilterProxyModel):

    def __init__(self, *args, **kwargs):
        super(ToolStackSortProxyModel, self).__init__(*args, **kwargs)
        self.setSortRole(ToolStackModel.ContextSortRole)

    def sort(self, column, order=QtCore.Qt.AscendingOrder):
        """

        :param column:
        :param order:
        :type column: int
        :type order: QtCore.Qt.SortOrder
        :return:
        """
        order = QtCore.Qt.DescendingOrder  # fixed
        return super(ToolStackSortProxyModel, self).sort(column, order)


class ResolvedPackagesModel(BaseItemModel):
    Headers = [
        "Name",
        "Version",
        "Released",
    ]

    PackageRole = QtCore.Qt.UserRole + 10

    def load(self, packages):
        self.clear()


class ResolvedEnvironmentModel(JsonModel):

    def load(self, data):
        # Convert PATH environment variables to lists
        # for improved viewing experience
        for key, value in data.copy().items():
            if os.pathsep in value:
                value = value.split(os.pathsep)
            data[key] = value

        super(ResolvedEnvironmentModel, self).load(data)


class InstalledPackagesModel(BaseItemModel, metaclass=QSingleton):
    """
    Note: This is a singleton.
    """
    family_updated = QtCore.Signal()
    FilterRole = QtCore.Qt.UserRole + 10
    ObjectRole = QtCore.Qt.UserRole + 11
    CompletionRole = QtCore.Qt.UserRole + 12
    Headers = [
        "Name",
        "Date",
    ]

    def __init__(self, *args, **kwargs):
        super(InstalledPackagesModel, self).__init__(*args, **kwargs)
        self._initials = dict()
        self._families = dict()

    def clear(self):
        self._initials.clear()
        self._families.clear()
        super(InstalledPackagesModel, self).clear()

    def initials(self):
        return sorted(self._initials.keys())

    def first_item_in_initial(self, letter):
        return self._initials.get(letter)

    def add_families(self, families):
        for family in sorted(families, key=lambda f: f.name.lower()):
            item = QtGui.QStandardItem(family.name)
            item.setData(family, self.ObjectRole)
            item.setData(family.name, self.CompletionRole)
            self.appendRow(item)

            self._families[family.name] = item

            initial = family.name[0].upper()
            if initial not in self._initials:
                self._initials[initial] = item

        self.family_updated.emit()

    def add_versions(self, versions):
        if not versions:
            return
        parent = self._families.get(versions[0].name)
        if not parent:
            return

        times = set()
        for version in sorted(versions, key=lambda v: v.version):
            times.add(version.timestamp)
            keys = "%s,%s" % (version.qualified, ",".join(version.tools))

            name_item = QtGui.QStandardItem(version.qualified)
            name_item.setData(keys, self.FilterRole)
            name_item.setData(version, self.ObjectRole)
            name_item.setData(str(version.version), self.CompletionRole)

            date_item = QtGui.QStandardItem()
            date_item.setData(version.timestamp, QtCore.Qt.DisplayRole)

            parent.appendRow([name_item, date_item])

        date_item = QtGui.QStandardItem()
        date_item.setData(sorted(times)[-1], QtCore.Qt.DisplayRole)
        self.setItem(parent.row(), 1, date_item)

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

        if role == self.ObjectRole:
            item = self.itemFromIndex(self.index(index.row(), 0))
            return item.data(self.ObjectRole)

        return super(InstalledPackagesModel, self).data(index, role)

    def flags(self, index):
        """

        :param index:
        :type index: QtCore.QModelIndex
        :return:
        :rtype: QtCore.Qt.ItemFlags
        """
        return QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable


class InstalledPackagesProxyModel(QtCore.QSortFilterProxyModel):

    def __init__(self, *args, **kwargs):
        super(InstalledPackagesProxyModel, self).__init__(*args, **kwargs)
        self.setFilterCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self.setSortCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self.setFilterRole(InstalledPackagesModel.FilterRole)
        self.setRecursiveFilteringEnabled(True)


class SuiteStorageModel(BaseItemModel):
    SuitePathRole = QtCore.Qt.UserRole + 10
    Headers = [
        "Name",
    ]

    def add_saved_suites(self, branch, suites):
        """

        :param branch:
        :param suites:
        :type branch: str
        :type suites: list[SavedSuite]
        :return:
        """
        branch_item = QtGui.QStandardItem(branch)
        self.appendRow(branch_item)

        for suite in suites:
            suite_item = QtGui.QStandardItem(suite.name)
            suite_item.setData(suite.path, self.SuitePathRole)
            branch_item.appendRow(suite_item)
