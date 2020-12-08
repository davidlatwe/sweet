
from ..vendor.Qt5 import QtCore, QtGui
from ..common.model import AbstractTableModel
from .. import resources as res

QtCheckState = QtCore.Qt.CheckState


class ToolItem(dict):
    def __init__(self, tool_name):
        data = {
            "name": tool_name,
            "alias": "",
            "hide": False,
            "conflict": False,
        }
        super(ToolItem, self).__init__(data)


class ToolModel(AbstractTableModel):

    ItemRole = QtCore.Qt.UserRole + 10
    ConflictRole = QtCore.Qt.UserRole + 11

    Headers = [
        "native",
        "expose",
    ]

    def __init__(self, parent=None):
        super(ToolModel, self).__init__(parent)
        self._prefix = ""
        self._suffix = ""
        self._icons = {
            "ok": res.icon("images", "check-ok"),
            "conflict": res.icon("images", "exclamation-warn"),
        }

    def _exposed_name(self, data):
        return data["alias"] or (self._prefix + data["name"] + self._suffix)

    def set_conflicting(self, conflicts):
        for row in range(self.rowCount()):
            index = self.createIndex(row, 1)
            self.setData(index, conflicts, role=self.ConflictRole)

    def set_prefix(self, text):
        first = self.createIndex(0, 1)
        last = self.createIndex(self.rowCount() - 1, 1)
        self._prefix = text
        self.dataChanged.emit(first, last)

    def set_suffix(self, text):
        first = self.createIndex(0, 1)
        last = self.createIndex(self.rowCount() - 1, 1)
        self._suffix = text
        self.dataChanged.emit(first, last)

    def iter_exposed_tools(self):
        for item in self.items:
            if not item["hide"]:
                yield self._exposed_name(item)

    def clear(self):
        self.beginResetModel()
        self.items.clear()
        self.endResetModel()

    def add_items(self, tools):
        self.beginResetModel()
        self.items += [ToolItem(name) for name in tools]
        self.endResetModel()

    def data(self, index, role=QtCore.Qt.DisplayRole):
        if not index.isValid():
            return None

        row = index.row()
        col = index.column()

        try:
            data = self.items[row]
        except IndexError:
            return None

        if role == self.ItemRole:
            return data.copy()

        if col == 0 and role == QtCore.Qt.CheckStateRole:
            return (QtCheckState.Checked if data["hide"]
                    else QtCheckState.Unchecked)

        if col == 1 and role == QtCore.Qt.FontRole:
            font = QtGui.QFont()
            font.setBold(bool(data["alias"]))
            return font

        if col == 1 and role == QtCore.Qt.DecorationRole:
            if not data["hide"]:
                if data["conflict"]:
                    return self._icons["conflict"]
                return self._icons["ok"]

        if col == 0 and role == QtCore.Qt.DisplayRole:
            return data["name"]

        if col == 1 and role in (QtCore.Qt.DisplayRole, QtCore.Qt.EditRole):
            if data["hide"]:
                return ""
            return self._exposed_name(data)

    def setData(self, index, value, role=QtCore.Qt.EditRole):
        row = index.row()
        col = index.column()

        try:
            data = self.items[row]
        except IndexError:
            return False

        if col == 1 and role == self.ConflictRole:
            conflicted = self._exposed_name(data) in value
            if data["conflict"] != conflicted:
                data["conflict"] = conflicted
                self.dataChanged.emit(index, index, [role])

        if col == 0 and role == QtCore.Qt.CheckStateRole:
            data["hide"] = True if value == QtCheckState.Checked else False
            self.dataChanged.emit(index, index.sibling(row, 1), [role])

        if col == 1 and role == QtCore.Qt.EditRole:
            value = value.strip()
            data["alias"] = "" if value == data["name"] else value
            self.dataChanged.emit(index, index, [role])

        return True

    def flags(self, index):
        if index.column() == 0:
            return (
                QtCore.Qt.ItemIsEnabled |
                QtCore.Qt.ItemIsUserCheckable
            )
        if index.column() == 1:
            return (
                QtCore.Qt.ItemIsEnabled |
                QtCore.Qt.ItemIsEditable
            )

    def load(self, hidden, aliases):
        items = self.items
        if not items:
            return

        hidden = hidden or set()
        aliases = aliases or dict()

        for row, tool in enumerate(items):
            name = tool["name"]
            is_hidden = name in hidden
            alias = aliases.get(name, "")
            roles = []

            if is_hidden:
                tool["hide"] = True
                roles.append(QtCore.Qt.CheckStateRole)

            if alias:
                tool["alias"] = alias
                roles.append(QtCore.Qt.EditRole)

            if roles:
                index = self.createIndex(row, 0)
                self.dataChanged.emit(index, index, roles)
