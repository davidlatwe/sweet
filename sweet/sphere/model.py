
from Qt5 import QtCore, QtGui
from ..common.model import AbstractTableModel
from .. import resources as res

QtCheckState = QtCore.Qt.CheckState


class ToolItem(dict):
    def __init__(self, context_name, tool_name):
        data = {
            "context": context_name,
            "name": tool_name,
            "alias": "",
            "hide": False,
        }
        super(ToolItem, self).__init__(data)


class ToolModel(AbstractTableModel):
    ItemRole = QtCore.Qt.UserRole + 10
    Headers = [
        "native",
        "expose",
    ]
    alias_changed = QtCore.Signal(str, str)
    hide_changed = QtCore.Signal(str, bool)

    def __init__(self, parent=None):
        super(ToolModel, self).__init__(parent)
        self._prefix = ""
        self._suffix = ""
        self._conflicts = []
        self._icons = {
            "ok": res.icon("images", "play-fill-ok"),
            "conflict": res.icon("images", "exclamation-triangle-fill"),
        }

    def _exposed_name(self, data):
        return data["alias"] or (self._prefix + data["name"] + self._suffix)

    def set_conflicting(self, conflicts):
        self._conflicts = conflicts[:]

    def set_prefix(self, text):
        self._prefix = text

    def set_suffix(self, text):
        self._suffix = text

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
                conflicted = self._exposed_name(data) in self._conflicts
                if conflicted:
                    return self._icons["conflict"]
                return self._icons["ok"]

        if col == 0 and role == QtCore.Qt.DisplayRole:
            return data["name"]

        if col == 1 and role == QtCore.Qt.DisplayRole:
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

        if col == 0 and role == QtCore.Qt.CheckStateRole:
            data["hide"] = True if value == QtCheckState.Checked else False
            self.dataChanged.emit(index, index.sibling(row, 1))
            self.hide_changed.emit(data["name"], data["hide"])

        if col == 1 and role == QtCore.Qt.EditRole:
            value = value.strip()
            data["alias"] = "" if value == data["name"] else value
            self.dataChanged.emit(index, index)
            self.alias_changed.emit(data["name"], data["alias"])

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


class ToolProxyModel(QtCore.QSortFilterProxyModel):

    def __init__(self, parent=None):
        super(ToolProxyModel, self).__init__(parent=parent)
        self._context_name = None

    def set_context(self, name):
        self._context_name = name

    def filterAcceptsRow(self, source_row, source_parent):
        pass
