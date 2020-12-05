
from Qt5 import QtCore, QtGui
from ..common.model import AbstractTreeModel, TreeItem

QtCheckState = QtCore.Qt.CheckState


class PackageItem(TreeItem):
    def __init__(self, data=None):
        super(PackageItem, self).__init__(data or {})
        self["_isChecked"] = QtCheckState.Unchecked


class PackageModel(AbstractTreeModel):
    FilterRole = QtCore.Qt.UserRole + 10
    CompletionRole = QtCore.Qt.UserRole + 11
    CompletionColumn = 0
    Headers = [
        "name",
        "date",
        "tools",
    ]

    def __init__(self, parent=None):
        super(PackageModel, self).__init__(parent=parent)
        self._groups = set()

    def name_groups(self):
        return sorted(self._groups)

    def iter_items(self):
        for item in self.root.children():
            yield item

    def reset(self, items=None):
        self.beginResetModel()
        self._groups.clear()
        family = None
        families = set()

        def cover_previous_family():
            if family:
                family["tools"] = ", ".join(sorted(family["tools"]))
                family["timestamp"] = sorted(family["timestamp"])[-1]
                family["date"] = family["timestamp"]

        for item in sorted(items or [], key=lambda i: i["family"].lower()):
            family_name = item["family"]
            tools = item["tools"][:]
            initial = family_name[0].upper()

            item.update({
                "_type": "version",
                "_group": initial,
                "name": item["qualified_name"],
                "tools": ", ".join(sorted(tools)),
                "date": item["timestamp"]
            })
            item = PackageItem(item)

            if family_name not in families:
                cover_previous_family()

                family = PackageItem({
                    "_type": "family",
                    "_group": initial,
                    "name": family_name,
                    "family": family_name,
                    "version": "",
                    "tools": set(),  # later be formatted from all versions
                    "timestamp": set(),  # later be sorted and get latest
                })

                families.add(family_name)
                self._groups.add(initial)
                self.add_child(family)

            family["tools"].update(tools)
            family["timestamp"].add(item["timestamp"])
            family.add_child(item)

        cover_previous_family()

        self.endResetModel()

    def data(self, index, role=QtCore.Qt.DisplayRole):
        if not index.isValid():
            return None

        if role == self.CompletionRole:
            item = index.internalPointer()
            if item["_type"] == "family":
                return item["family"]
            else:
                return item["version"]

        if role == QtCore.Qt.DisplayRole:
            col = index.column()
            item = index.internalPointer()
            key = self.Headers[col]
            return item[key]

        if role == QtCore.Qt.ForegroundRole:
            col = index.column()
            item = index.internalPointer()
            if item["_type"] == "version" and col == 0:
                return QtGui.QColor("gray")

        if role == QtCore.Qt.CheckStateRole:
            if index.column() == 0:
                item = index.internalPointer()
                return item["_isChecked"]

        if role == self.FilterRole:
            item = index.internalPointer()
            return ", ".join([item["family"], item["tools"]])

    def setData(self, index, value, role=QtCore.Qt.EditRole):
        if role == QtCore.Qt.CheckStateRole:
            if index.column() == 0:
                parent = index.parent()
                item = index.internalPointer()
                item["_isChecked"] = value

                if parent.isValid():
                    # Was ticking on version, update version and family
                    family = parent.internalPointer()
                    versions = family.children()

                    if any(v["_isChecked"] == QtCheckState.Checked
                           for v in versions):
                        family["_isChecked"] = QtCheckState.PartiallyChecked
                    else:
                        family["_isChecked"] = QtCheckState.Unchecked

                    self.dataChanged.emit(index, index)
                    self.dataChanged.emit(parent, parent)

                else:
                    # Was ticking on family, means *any* version
                    versions = item.children()

                    # un-tick all versions
                    for version in versions:
                        version["_isChecked"] = QtCheckState.Unchecked

                    first = index.child(0, 0)
                    last = index.child(len(versions) - 1, 0)
                    self.dataChanged.emit(first, last)
                    self.dataChanged.emit(index, index)

        return super(PackageModel, self).setData(index, value, role)

    def flags(self, index):
        if index.column() == 0:
            return (
                QtCore.Qt.ItemIsEnabled |
                QtCore.Qt.ItemIsSelectable |
                QtCore.Qt.ItemIsUserCheckable
            )

        return super(PackageModel, self).flags(index)


class PackageProxyModel(QtCore.QSortFilterProxyModel):

    def __init__(self, parent=None):
        super(PackageProxyModel, self).__init__(parent=parent)
        self.setFilterCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self.setSortCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self.setFilterRole(PackageModel.FilterRole)
