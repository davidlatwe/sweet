

from ..gui.vendor.Qt5 import QtCore, QtGui


class SuiteModel(QtGui.QStandardItemModel):
    pass


class ContextStackModel(QtGui.QStandardItemModel):
    Headers = [
        "Name",
        "Prefix",
        "Suffix",
        "Loaded",
    ]

    def __init__(self, *args, **kwargs):
        super(ContextStackModel, self).__init__(*args, **kwargs)
        self.setColumnCount(len(self.Headers))

    def headerData(self, section, orientation, role=QtCore.Qt.DisplayRole):
        if role == QtCore.Qt.DisplayRole:
            return self.Headers[section]
        return super(ContextStackModel, self).headerData(
            section, orientation, role)

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


class ToolStackModel(QtGui.QStandardItemModel):
    Headers = [
        "Alias",
        "Name",
        "Context",
        "Status",
    ]

    def __init__(self, *args, **kwargs):
        super(ToolStackModel, self).__init__(*args, **kwargs)
        self.setColumnCount(len(self.Headers))

    def headerData(self, section, orientation, role=QtCore.Qt.DisplayRole):
        if role == QtCore.Qt.DisplayRole:
            return self.Headers[section]
        return super(ToolStackModel, self).headerData(
            section, orientation, role)
