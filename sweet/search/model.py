
from Qt5 import QtCore, QtGui
from ..common.model import AbstractTreeModel, TreeItem

QtCheckState = QtCore.Qt.CheckState


class PackageItem(TreeItem):

    def add_child(self, child):
        child._parent = self
        for sibling in self._children:
            if sibling["version"] == child["version"]:
                # merge
                sibling["uri"] += child["uri"]
                break
        else:
            self._children.append(child)


class PackageModel(AbstractTreeModel):
    FilterRole = QtCore.Qt.UserRole + 10
    Headers = [
        "name",
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

        def complete_last_family():
            if family:
                family["tools"] = ", ".join(sorted(family["tools"]))
                all_versions = PackageItem({
                    "_type": "version",
                    "name": family["name"] + " [any]",
                    "family": family["family"],
                    "version": "*",
                    "tools": "",
                })
                family.add_child(all_versions)

        for item in sorted(items or [], key=lambda i: i["family"].lower()):
            family_name = item["family"]
            tools = item["tools"][:]
            initial = family_name[0].upper()

            item.update({
                "_type": "version",
                "_group": initial,
                "name": item["qualified_name"],
                "tools": ", ".join(sorted(tools)),
                "uri": [item["uri"]]
            })
            item = PackageItem(item)

            if family_name not in families:
                complete_last_family()

                family = PackageItem({
                    "_type": "family",
                    "_group": initial,
                    "name": family_name,
                    "family": family_name,
                    "version": "",
                    "tools": set(),
                })

                families.add(family_name)
                self._groups.add(initial)
                self.add_child(family)

            family["tools"].update(tools)
            family.add_child(item)

        complete_last_family()

        self.endResetModel()

    def data(self, index, role=QtCore.Qt.DisplayRole):
        if not index.isValid():
            return None

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
                return item.get("_isChecked", QtCheckState.Unchecked)

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
                    # Was ticking on version, update versions and family
                    family = parent.internalPointer()
                    versions = family.children()
                    is_any = (len(versions) - 1) == index.row()

                    if is_any:
                        # version *any* ticked, un-tick all other versions
                        for c in versions[:-1]:
                            c["_isChecked"] = QtCheckState.Unchecked
                    else:
                        # other version ticked, un-tick version *any*
                        versions[-1]["_isChecked"] = QtCheckState.Unchecked

                    states = set([
                        version.get("_isChecked", QtCheckState.Unchecked)
                        for version in versions
                    ])
                    if is_any:
                        family["_isChecked"] = value
                    elif len(states) > 1:
                        family["_isChecked"] = QtCheckState.PartiallyChecked
                    else:
                        family["_isChecked"] = QtCheckState.Unchecked

                    first = parent.child(0, 0)
                    last = parent.child(len(versions) - 1, 0)
                    self.dataChanged.emit(first, last)
                    self.dataChanged.emit(parent, parent)

                else:
                    # Was ticking on family, update versions
                    versions = item.children()

                    # un-tick all versions
                    for version in versions:
                        version["_isChecked"] = QtCheckState.Unchecked

                    if value == QtCheckState.Checked:
                        # family activated, tick version *any*
                        versions[-1]["_isChecked"] = QtCheckState.Checked

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
        self.setFilterRole(PackageModel.FilterRole)
