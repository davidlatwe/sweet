
import os
from ._vendor.Qt5 import QtCore, QtGui
from ._vendor import qjsonmodel


class BaseItemModel(QtGui.QStandardItemModel):
    Headers = []

    def __init__(self, *args, **kwargs):
        super(BaseItemModel, self).__init__(*args, **kwargs)
        self.setColumnCount(len(self.Headers))

    def headerData(self, section, orientation, role=QtCore.Qt.DisplayRole):
        if role == QtCore.Qt.DisplayRole:
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

    def flags(self, index):
        if index.isValid():
            # we don't want to drop in as a child item so the flag
            # `ItemIsDropEnabled` is omitted.
            return (
                QtCore.Qt.ItemIsEnabled |
                QtCore.Qt.ItemIsSelectable |
                QtCore.Qt.ItemIsDragEnabled
            )
        else:
            return (
                QtCore.Qt.ItemIsEnabled |
                QtCore.Qt.ItemIsSelectable |
                QtCore.Qt.ItemIsDropEnabled
            )


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
