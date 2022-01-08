
import os
from ._vendor.Qt5 import QtCore, QtGui
from ._vendor import qjsonmodel


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


class TreeItem(dict):

    def __init__(self, data=None):
        super(TreeItem, self).__init__(data or {})
        self._children = list()
        self._parent = None

    def row(self):
        if self._parent is not None:
            siblings = self.parent().children()
            return siblings.index(self)

    def parent(self):
        return self._parent

    def child(self, row):
        if row >= len(self._children):
            print("Invalid row as child: {0}".format(row))
            return
        return self._children[row]

    def children(self):
        return self._children

    def childCount(self):
        return len(self._children)

    def add_child(self, child):
        child._parent = self
        self._children.append(child)


class AbstractTreeModel(QtCore.QAbstractItemModel):
    Headers = []

    def __init__(self, parent=None):
        super(AbstractTreeModel, self).__init__(parent)
        self.root = TreeItem()

    def reset(self, items=None):
        pass

    def rowCount(self, parent=QtCore.QModelIndex()):
        if parent.isValid():
            item = parent.internalPointer()
        else:
            item = self.root

        return item.childCount()

    def columnCount(self, parent=QtCore.QModelIndex()):
        return len(self.Headers)

    def index(self, row, column, parent=QtCore.QModelIndex()):
        if not parent.isValid():
            parent_item = self.root
        else:
            parent_item = parent.internalPointer()

        child_item = parent_item.child(row)
        if child_item:
            return self.createIndex(row, column, child_item)
        else:
            return QtCore.QModelIndex()

    def headerData(self, section, orientation, role=QtCore.Qt.DisplayRole):
        if role == QtCore.Qt.DisplayRole and section < len(self.Headers):
            return self.Headers[section]
        return super(AbstractTreeModel, self).headerData(
            section, orientation, role)

    def data(self, index, role=QtCore.Qt.DisplayRole):
        if not index.isValid():
            return None

        if role == QtCore.Qt.DisplayRole:
            item = index.internalPointer()
            col = index.column()
            key = self.Headers[col]
            return item[key]

    def parent(self, index=QtCore.QModelIndex()):
        if not index.isValid():
            return None

        item = index.internalPointer()
        parent_item = item.parent()

        # If it has no parents we return invalid
        if parent_item == self.root or not parent_item:
            return QtCore.QModelIndex()

        return self.createIndex(parent_item.row(), 0, parent_item)

    def add_child(self, item, parent=None):
        if parent is None:
            parent = self.root

        parent.add_child(item)


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


class ToolStackModel(BaseItemModel):
    Headers = [
        "Name",
        "Status",
    ]


class ResolvedPackagesModel(BaseItemModel):
    Headers = [
        "Name",
        "Version",
        "Released",
    ]

    PackageRole = QtCore.Qt.UserRole + 10


class ResolvedToolsModel(BaseItemModel):
    pass


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
        if not index.isValid():
            return

        if role == self.ObjectRole:
            item = self.itemFromIndex(self.index(index.row(), 0))
            return item.data(self.ObjectRole)

        return super(InstalledPackagesModel, self).data(index, role)

    def flags(self, index):
        return QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable


class InstalledPackagesProxyModel(QtCore.QSortFilterProxyModel):

    def __init__(self, *args, **kwargs):
        super(InstalledPackagesProxyModel, self).__init__(*args, **kwargs)
        self.setFilterCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self.setSortCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self.setFilterRole(InstalledPackagesModel.FilterRole)
        self.setRecursiveFilteringEnabled(True)
