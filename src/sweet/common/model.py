
from ..vendor.Qt5 import QtCore
from ..vendor import qjsonmodel


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
        if role == QtCore.Qt.DisplayRole:
            return self.Headers[section]

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


class AbstractTableModel(QtCore.QAbstractTableModel):
    Headers = []

    def __init__(self, parent=None):
        super(AbstractTableModel, self).__init__(parent)
        self.items = []

    def reset(self, items=None):
        pass

    def find(self, name):
        return next(i for i in self.items if i["name"] == name)

    def findIndex(self, name, column=0):
        row = self.items.index(self.find(name))
        return self.createIndex(row, column, QtCore.QModelIndex())

    def rowCount(self, parent=QtCore.QModelIndex()):
        if parent.isValid():
            return 0

        return len(self.items)

    def columnCount(self, parent=None):
        return len(self.Headers)

    def headerData(self, section, orientation, role=QtCore.Qt.DisplayRole):
        if orientation == QtCore.Qt.Vertical:
            return

        if role == QtCore.Qt.DisplayRole:
            return self.Headers[section]


class CompleterProxyModel(QtCore.QSortFilterProxyModel):
    def data(self, index, role=QtCore.Qt.DisplayRole):
        if role == QtCore.Qt.CheckStateRole:  # disable checkbox
            return
        return super(CompleterProxyModel, self).data(index, role)


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
