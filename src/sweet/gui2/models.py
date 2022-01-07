
import os
from ._vendor.Qt5 import QtCore, QtGui
from ._vendor import qjsonmodel


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


class ContextStackModel(BaseItemModel):
    Headers = [
        "Name",
        "Prefix",
        "Suffix",
        "Loaded",
    ]

    ItemRole = QtCore.Qt.UserRole + 10

    def supportedDropActions(self):
        return QtCore.Qt.MoveAction

    def flags(self, index):
        base_flags = (
            QtCore.Qt.ItemIsEnabled |
            QtCore.Qt.ItemIsSelectable
        )
        if index.isValid():
            # we don't want to drop in as a child item so the flag
            # `ItemIsDropEnabled` is omitted.
            return base_flags | QtCore.Qt.ItemIsDragEnabled
        else:
            return base_flags | QtCore.Qt.ItemIsDropEnabled

    def data(self, index, role=QtCore.Qt.DisplayRole):
        if not index.isValid():
            return

        if role in {QtCore.Qt.DisplayRole, QtCore.Qt.EditRole}:

            item_index = self.index(index.row(), 0)
            ctx = item_index.data(self.ItemRole)
            if ctx is None:
                return

            column = index.column()
            if column == 0:
                return ctx.name
            if column == 1:
                return ctx.prefix
            if column == 2:
                return ctx.suffix
            if column == 3:
                return ctx.loaded

        return super(ContextStackModel, self).data(index, role)

    def context_names(self, indexes=None):
        indexes = indexes if indexes is not None else [
            self.index(row, 0) for row in range(self.rowCount())
        ]
        return [self.data(index) for index in indexes]


class ToolStackModel(BaseItemModel):
    Headers = [
        "Alias",
        "Name",
        "Context",
        "Status",
    ]


class ResolvedPackagesModel(BaseItemModel):
    Headers = [
        "Name",
        "Version",
        "Released",
    ]

    PackageRole = QtCore.Qt.UserRole + 10


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


class ResolvedEnvironmentModel(JsonModel):

    def load(self, data):
        # Convert PATH environment variables to lists
        # for improved viewing experience
        for key, value in data.copy().items():
            if os.pathsep in value:
                value = value.split(os.pathsep)
            data[key] = value

        super(ResolvedEnvironmentModel, self).load(data)
