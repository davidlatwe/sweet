
from ..vendor.Qt5 import QtCore
from ..common.model import AbstractTableModel


class SuiteDraftItem(dict):

    def __init__(self, data):
        super(SuiteDraftItem, self).__init__({
            "name": data["name"],
            "root": data["root"],
            "path": data["path"],
            "description": data["description"],
        })


class SuiteDraftModel(AbstractTableModel):
    DescriptionRole = QtCore.Qt.UserRole + 10
    ItemRole = QtCore.Qt.UserRole + 11
    Headers = [
        "name",
    ]

    def clear(self):
        self.beginResetModel()
        self.items.clear()
        self.endResetModel()

    def add_items(self, items):
        self.beginResetModel()
        self.items += [SuiteDraftItem(data) for data in items]
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

        if col == 0 and role == QtCore.Qt.DisplayRole:
            return data["name"]

        if role == self.DescriptionRole:
            return data["description"]

        if role == self.ItemRole:
            return data
