
from Qt5 import QtCore, QtWidgets


class VerticalDocTabBar(QtWidgets.QTabBar):

    def __init__(self, parent=None):
        QtWidgets.QTabBar.__init__(self, parent=parent)
        self.setShape(QtWidgets.QTabBar.RoundedWest)
        self.setDocumentMode(True)  # for MacOS
        self.setUsesScrollButtons(True)

    def tabSizeHint(self, index):
        s = QtWidgets.QTabBar.tabSizeHint(self, index)
        s.transpose()
        return s

    def paintEvent(self, event):
        painter = QtWidgets.QStylePainter(self)
        opt = QtWidgets.QStyleOptionTab()

        for i in range(self.count()):
            self.initStyleOption(opt, i)
            painter.drawControl(QtWidgets.QStyle.CE_TabBarTabShape, opt)
            painter.save()

            s = opt.rect.size()
            s.transpose()
            r = QtCore.QRect(QtCore.QPoint(), s)
            r.moveCenter(opt.rect.center())
            opt.rect = r

            rect = self.tabRect(i)
            c = rect.center()
            painter.translate(c)
            painter.rotate(90)
            painter.translate(-c)
            painter.drawControl(QtWidgets.QStyle.CE_TabBarTabLabel, opt)
            painter.restore()


class VerticalExtendedTreeView(QtWidgets.QTreeView):
    """TreeView with vertical virtual space extended

    The last row in default TreeView always stays on bottom, this TreeView
    subclass extends the space so the last row can be scrolled on top of
    view. Which behaves like modern text editor that has virtual space after
    last line.

    TODO: What about other AbstractItemView subclass ?

    """
    _extended = None
    _on_key_search = False

    def __init__(self, parent=None):
        super(VerticalExtendedTreeView, self).__init__(parent=parent)
        # these are important
        self.setVerticalScrollMode(self.ScrollPerPixel)
        self.setSizeAdjustPolicy(self.AdjustIgnored)
        self.setUniformRowHeights(True)

        self.collapsed.connect(self.reset_extension)
        self.expanded.connect(self.reset_extension)

        self._on_key_search = False
        self._extended = None
        self._row_height = 0
        self._pos = 0

    def _compute_extension(self):
        # scrollArea's SizeAdjustPolicy is AdjustIgnored, so the extension
        # only need to set once until modelReset or item collapsed/expanded
        scroll = self.verticalScrollBar()
        height = self.viewport().height()
        row_unit = self.uniformed_row_height()
        current_max = scroll.maximum()
        if current_max:
            self._extended = current_max + height - row_unit
        else:
            self._extended = 0

    def paintEvent(self, event):
        if self._extended is None:
            self._compute_extension()

        if self._extended > 0:
            scroll = self.verticalScrollBar()
            current_max = scroll.maximum()

            resized = self._extended != current_max
            if resized:
                scroll.setMaximum(self._extended)
                scroll.setSliderPosition(self._pos)
            else:
                self._pos = scroll.sliderPosition()

        return super(VerticalExtendedTreeView, self).paintEvent(event)

    def setModel(self, model):
        super(VerticalExtendedTreeView, self).setModel(model)
        model.modelReset.connect(self.reset_extension)

    def uniformed_row_height(self):
        """Uniformed single row height, compute from first row and cached"""
        if not self._row_height:
            model = self.model()
            first = model.index(0, 0)
            self._row_height = float(self.rowHeight(first))
        # cached
        return self._row_height

    def reset_extension(self, *args, **kwargs):
        """Should be called on model reset or item collapsed/expanded"""
        self._extended = None

    def scroll_at_top(self, index):
        """Scroll to index and position at top
        Like `scrollTo` with `PositionAtTop` hint, but works better with
        extended view.
        """
        if self._extended:
            scroll = self.verticalScrollBar()
            rect = self.visualRect(index)
            pos = rect.top() + self.verticalOffset()
            scroll.setSliderPosition(pos)
        else:
            hint = self.PositionAtTop
            super(VerticalExtendedTreeView, self).scrollTo(index, hint)

    def scrollTo(self, index, hint=None):
        hint = hint or self.EnsureVisible
        if hint == self.PositionAtTop or self._on_key_search:
            self.scroll_at_top(index)
        else:
            super(VerticalExtendedTreeView, self).scrollTo(index, hint)

    def keyboardSearch(self, string):
        self._on_key_search = True
        super(VerticalExtendedTreeView, self).keyboardSearch(string)
        self._on_key_search = False

    def top_scrolled_index(self, value):
        """Return the index of item that has scrolled in top of view"""
        row_unit = self.uniformed_row_height()
        value = (value - self.verticalOffset()) / row_unit
        return self.indexAt(QtCore.QPoint(0, value))
