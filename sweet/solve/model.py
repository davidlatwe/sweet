
import os
from ..vendor.Qt5 import QtCore
from ..common.model import AbstractTableModel, JsonModel


class PackageItem(dict):

    def __init__(self, package):
        super(PackageItem, self).__init__({
            "name": package.name,
            "version": str(package.version),
            "package": package,
        })


class ResolvedPackageModel(AbstractTableModel):

    PackageRole = QtCore.Qt.UserRole + 10

    Headers = [
        "name",
        "version",
    ]

    def clear(self):
        self.beginResetModel()
        self.items.clear()
        self.endResetModel()

    def add_items(self, packages):
        self.beginResetModel()
        self.items += [PackageItem(pkg) for pkg in packages]
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

        if role == self.PackageRole:
            return data["package"]

        if col == 0 and role == QtCore.Qt.DisplayRole:
            return data["name"]

        if col == 1 and role == QtCore.Qt.DisplayRole:
            return data["version"]

    def flags(self, index):
        # not selectable
        return (
                QtCore.Qt.ItemIsEnabled
        )


class EnvironmentModel(JsonModel):
    def load(self, data):
        # Convert PATH environment variables to lists
        # for improved viewing experience
        for key, value in data.copy().items():
            if os.pathsep in value:
                value = value.split(os.pathsep)
            data[key] = value

        super(EnvironmentModel, self).load(data)
