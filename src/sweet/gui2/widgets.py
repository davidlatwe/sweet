
from ..gui.vendor.Qt5 import QtWidgets, QtCore
from typing import TypedDict


class CurrentSuite(QtWidgets.QWidget):
    object_name = "SuiteView"

    def __init__(self, parent=None, flags=QtCore.Qt.Widget):
        super(CurrentSuite, self).__init__(parent=parent, flags=flags)
        self.setObjectName(self.object_name)

        class Widgets(TypedDict):
            name: QtWidgets.QLineEdit

        # todo: use dataklass
        widgets = Widgets(
            name=QtWidgets.QLineEdit(),
        )
