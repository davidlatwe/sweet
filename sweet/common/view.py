
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


class Spoiler(QtWidgets.QWidget):
    """
    Referenced from https://stackoverflow.com/a/37927256
    """
    def __init__(self, parent=None, title="", duration=100):
        super(Spoiler, self).__init__(parent=parent)
        self.setObjectName("Spoiler")

        widgets = {
            "head": SpoilerHead(title=title),
            "body": QtWidgets.QScrollArea(),
        }
        widgets["body"].setWidgetResizable(True)

        # start out collapsed
        widgets["body"].setMaximumHeight(0)
        widgets["body"].setMinimumHeight(0)
        # let the entire widget grow and shrink with its content
        anim = QtCore.QParallelAnimationGroup()
        for q_obj, property_ in [(self, b"minimumHeight"),
                                 (self, b"maximumHeight"),
                                 (widgets["body"], b"maximumHeight")]:
            anim.addAnimation(QtCore.QPropertyAnimation(q_obj, property_))

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(widgets["head"])
        layout.addWidget(widgets["body"], stretch=True)
        layout.setSpacing(0)

        def start_animation(checked):
            direction = (QtCore.QAbstractAnimation.Forward if checked
                         else QtCore.QAbstractAnimation.Backward)
            anim.setDirection(direction)
            anim.start()

        widgets["head"].clicked.connect(start_animation)

        self._widgets = widgets
        self._anim = anim
        self._duration = duration

    def set_content(self, widget):
        body = self._widgets["body"]
        anim = self._anim

        layout = QtWidgets.QHBoxLayout()
        layout.addWidget(widget)

        body.destroy()
        body.setLayout(layout)
        collapsed_height = self.sizeHint().height() - body.maximumHeight()
        content_height = layout.sizeHint().height() + 20

        for i in range(anim.animationCount() - 1):
            spoiler_anim = anim.animationAt(i)
            spoiler_anim.setDuration(self._duration)
            spoiler_anim.setStartValue(collapsed_height)
            spoiler_anim.setEndValue(collapsed_height + content_height)

        content_anim = anim.animationAt(anim.animationCount() - 1)
        content_anim.setDuration(self._duration)
        content_anim.setStartValue(0)
        content_anim.setEndValue(content_height)

        widget.destroyed.connect(self.deleteLater)

    def set_expanded(self, expand):
        self._widgets["head"].set_opened(expand)


class SpoilerHead(QtWidgets.QWidget):
    """
    |> title --------------------
    """
    clicked = QtCore.Signal(bool)

    def __init__(self, parent=None, title=""):
        super(SpoilerHead, self).__init__(parent=parent)
        self.setObjectName("SpoilerHead")

        widgets = {
            "toggle": QtWidgets.QToolButton(),
            "separator": QtWidgets.QFrame(),
        }
        widgets["separator"].setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Maximum)
        widgets["toggle"].setToolButtonStyle(
            QtCore.Qt.ToolButtonTextBesideIcon)

        widgets["separator"].setFrameShape(QtWidgets.QFrame.HLine)
        widgets["separator"].setFrameShadow(QtWidgets.QFrame.Sunken)
        widgets["toggle"].setArrowType(QtCore.Qt.RightArrow)
        widgets["toggle"].setText(str(title))

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(widgets["toggle"])
        layout.addWidget(widgets["separator"], stretch=True)
        layout.setSpacing(0)

        self._widgets = widgets
        self._opened = False
        self._hovered = False
        self._widgets["toggle"].installEventFilter(self)

    def set_opened(self, checked):
        toggle = self._widgets["toggle"]
        arrow_type = QtCore.Qt.DownArrow if checked else QtCore.Qt.RightArrow

        toggle.setArrowType(arrow_type)
        state = "open" if checked else "close"
        state += ".on" if self._hovered else ""
        toggle.setProperty("state", state)
        self.style().unpolish(toggle)
        self.style().polish(toggle)

        self._opened = checked
        self.clicked.emit(checked)

    def mouseReleaseEvent(self, event):
        self.set_opened(not self._opened)
        return super(SpoilerHead, self).mouseReleaseEvent(event)

    def enterEvent(self, event):
        toggle = self._widgets["toggle"]
        toggle.setProperty("state", "open.on" if self._opened else "close.on")
        self.style().unpolish(toggle)
        self.style().polish(toggle)
        self._hovered = True
        return super(SpoilerHead, self).enterEvent(event)

    def leaveEvent(self, event):
        toggle = self._widgets["toggle"]
        toggle.setProperty("state", "open" if self._opened else "close")
        self.style().unpolish(toggle)
        self.style().polish(toggle)
        self._hovered = False
        return super(SpoilerHead, self).leaveEvent(event)

    def eventFilter(self, obj, event):
        if event.type() == QtCore.QEvent.MouseButtonRelease:
            self.set_opened(not self._opened)
            return True

        return super(SpoilerHead, self).eventFilter(obj, event)
