
from .Qt5 import QtCore, QtWidgets


class VerticalExtendedTreeView(QtWidgets.QTreeView):
    """TreeView with vertical virtual space extended

    The last row in default TreeView always stays on bottom, this TreeView
    subclass extends the space so the last row can be scrolled on top of
    view. Which behaves like modern text editor that has virtual space after
    last line.

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

        self._extended = current_max + height - row_unit

    def paintEvent(self, event):
        if self._extended is None:
            self._compute_extension()

        if self._extended > 0:
            scroll = self.verticalScrollBar()
            current_max = scroll.maximum()

            resized = self._extended != current_max
            if resized and current_max > 0:
                scroll.setMaximum(self._extended)
                scroll.setSliderPosition(self._pos)
            else:
                self._pos = scroll.sliderPosition()

        return super(VerticalExtendedTreeView, self).paintEvent(event)

    def resizeEvent(self, event):
        self.reset_extension()
        return super(VerticalExtendedTreeView, self).resizeEvent(event)

    def setModel(self, model):
        super(VerticalExtendedTreeView, self).setModel(model)
        model.modelReset.connect(self.reset_extension)

    def uniformed_row_height(self):
        """Uniformed single row height, compute from first row and cached"""
        model = self.model()
        if model is not None and not self._row_height:
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

    def top_scrolled_index(self, slider_pos):
        """Return the index of item that has been scrolled of top of view"""
        row_unit = self.uniformed_row_height()
        value = (slider_pos - self.verticalOffset()) / row_unit
        return self.indexAt(QtCore.QPoint(0, value))
