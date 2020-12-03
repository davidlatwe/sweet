
from Qt5 import QtWidgets


class TableViewRowHover(QtWidgets.QStyledItemDelegate):

    def __init__(self, parent=None):
        super(TableViewRowHover, self).__init__(parent)
        self.view = None
        self._col = None

    def paint(self, painter, option, index):
        row = index.row()
        column = index.column()

        if option.state & QtWidgets.QStyle.State_MouseOver:
            self._col = column
            while True:
                super(TableViewRowHover, self).paint(painter, option, index)
                if column == 0:
                    break
                column -= 1  # repaint previous columns
                index = index.sibling(row, column)
                option.rect = self.view.visualRect(index)

        else:
            if self._col is not None and column > self._col:
                # hover the reset of columns
                option.state |= QtWidgets.QStyle.State_MouseOver
            else:
                self._col = None

            super(TableViewRowHover, self).paint(painter, option, index)
