
import os
from ..vendor.Qt5 import QtCore
from ..common.model import AbstractTableModel
from .. import _rezapi as rez, util


class SavedSuiteItem(dict):

    def __init__(self, data):
        super(SavedSuiteItem, self).__init__({
            "name": data["name"],
            "root": data["root"],
            "path": data["path"],
            "file": data["file"],
            "description": data["description"],
        })


class SavedSuiteModel(AbstractTableModel):
    DescriptionRole = QtCore.Qt.UserRole + 10
    ItemRole = QtCore.Qt.UserRole + 11
    Headers = [
        "name",
        "description",
    ]

    def clear(self):
        self.beginResetModel()
        self.items.clear()
        self.endResetModel()

    def add_files(self, suite_files, clear=True):
        self.beginResetModel()
        if clear:
            self.items.clear()

        existed = set(i["file"] for i in self.items)

        for filepath in suite_files:
            filepath = util.normpath(filepath)
            if filepath in existed:
                continue
            existed.add(filepath)

            description = rez.read_suite_description(filepath)
            suite_dir, suite_yaml = os.path.split(filepath)
            suite_root, suite_name = os.path.split(suite_dir)

            item = SavedSuiteItem({
                "name": suite_name,
                "root": suite_root,
                "path": suite_dir,
                "file": filepath,
                "description": description,
            })
            self.items.append(item)

        self.items.sort(key=lambda i: i["name"])

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
