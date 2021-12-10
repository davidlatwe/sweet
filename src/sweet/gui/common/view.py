
import json
from functools import partial
from ..vendor.Qt5 import QtCore, QtGui, QtWidgets
from .model import JsonModel
from . import delegate
from .. import resources as res
from ..vendor import qargparse


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
        layout.setContentsMargins(0, 6, 0, 12)
        layout.setSpacing(0)

        body.destroy()
        body.setLayout(layout)
        collapsed_height = self.sizeHint().height() - body.maximumHeight()
        content_height = layout.sizeHint().height()

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

    def set_title(self, title):
        self._widgets["head"].set_title(title)


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
        widgets["toggle"].setText(title)

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(widgets["toggle"])
        layout.addWidget(widgets["separator"], stretch=True)
        layout.setSpacing(0)

        self._widgets = widgets
        self._opened = False
        self._hovered = False
        self._widgets["toggle"].installEventFilter(self)

    def set_title(self, title):
        self._widgets["toggle"].setText(title)

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
        separator = self._widgets["separator"]
        separator.setFrameShadow(QtWidgets.QFrame.Plain)
        separator.setProperty("state", "on")
        self.style().unpolish(separator)
        self.style().polish(separator)

        toggle = self._widgets["toggle"]
        toggle.setProperty("state", "open.on" if self._opened else "close.on")
        self.style().unpolish(toggle)
        self.style().polish(toggle)

        self._hovered = True
        return super(SpoilerHead, self).enterEvent(event)

    def leaveEvent(self, event):
        separator = self._widgets["separator"]
        separator.setFrameShadow(QtWidgets.QFrame.Sunken)
        separator.setProperty("state", "")
        self.style().unpolish(separator)
        self.style().polish(separator)

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


class SlimTableView(QtWidgets.QTableView):

    def __init__(self, parent=None):
        super(SlimTableView, self).__init__(parent)
        self.setShowGrid(False)
        self.verticalHeader().hide()
        self.setSelectionMode(self.SingleSelection)
        self.setSelectionBehavior(self.SelectRows)
        self.setVerticalScrollMode(self.ScrollPerPixel)
        self.setHorizontalScrollMode(self.ScrollPerPixel)

        header = self.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(QtWidgets.QHeaderView.Stretch)

    def setItemDelegate(self, delegator):
        super(SlimTableView, self).setItemDelegate(delegator)
        if isinstance(delegator, delegate.TableViewRowHover):
            delegator.view = self


class RequestCompleter(QtWidgets.QCompleter):

    def splitPath(self, path):
        # TODO: "==", "+<", "..", ...
        return path.split("-", 1)


class CompleterPopup(QtWidgets.QListView):
    def __init__(self, parent=None):
        super(CompleterPopup, self).__init__(parent=parent)
        self.setObjectName("CompleterPopup")
        # this seems to be the only way to apply stylesheet to completer
        # popup.
        # TODO: make theme cache
        self.setStyleSheet(res.load_theme())


class RequestTextEdit(QtWidgets.QTextEdit):
    # keep this in Gist

    def __init__(self, parent=None):
        super(RequestTextEdit, self).__init__(parent=parent)
        self.setObjectName("RequestTextEdit")
        self._completer = None

    def setCompleter(self, c):
        if self._completer is not None:
            self._completer.activated.disconnect()

        self._completer = c

        c.setPopup(CompleterPopup())
        c.setWidget(self)
        c.setCompletionMode(QtWidgets.QCompleter.PopupCompletion)
        c.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
        c.activated.connect(self.insert_completion)

    def completer(self):
        return self._completer

    def insert_completion(self, completion):
        completer = self._completer
        if completer.widget() is not self:
            return

        prefix = completer.completionPrefix()
        prefix = completer.splitPath(prefix)[-1]
        extra = len(completion) - len(prefix)

        if extra is not 0:
            tc = self.textCursor()
            tc.movePosition(QtGui.QTextCursor.Left)
            tc.movePosition(QtGui.QTextCursor.EndOfWord)
            tc.insertText(completion[-extra:])
            self.setTextCursor(tc)

    def text_under_cursor(self):
        tc = self.textCursor()
        # can't use `QTextCursor.WordUnderCursor`, text like "maya-" that
        # ends with "-" will not be recognized as a word.
        tc.select(QtGui.QTextCursor.LineUnderCursor)
        text = tc.selectedText().rsplit(" ", 1)[-1]
        return text

    def focusInEvent(self, event):
        if self._completer is not None:
            self._completer.setWidget(self)

        super(RequestTextEdit, self).focusInEvent(event)

    def keyPressEvent(self, event):
        c = self._completer
        if c is not None and c.popup().isVisible():
            # The following keys are forwarded by the completer to the widget.
            if event.key() in (QtCore.Qt.Key_Escape,
                               QtCore.Qt.Key_Enter,
                               QtCore.Qt.Key_Return,
                               QtCore.Qt.Key_Backtab,
                               QtCore.Qt.Key_Tab):
                event.ignore()
                # Let the completer do default behavior.
                return

        is_shortcut = ((event.modifiers() & QtCore.Qt.ControlModifier) != 0
                       and event.key() == QtCore.Qt.Key_0)
        if c is None or not is_shortcut:
            # Do not process the shortcut when we have a completer.
            super(RequestTextEdit, self).keyPressEvent(event)

        ctrl_or_shift = event.modifiers() & (QtCore.Qt.ControlModifier
                                             | QtCore.Qt.ShiftModifier)
        if c is None or (ctrl_or_shift and len(event.text()) == 0):
            return

        end_of_word = " "  # "~!@#$%^&*()_+{}|:\"<>?,./;'[]\\-="
        has_modifier = ((event.modifiers() != QtCore.Qt.NoModifier)
                        and not ctrl_or_shift)
        completion_prefix = self.text_under_cursor()

        if (not is_shortcut and (has_modifier
                                 or len(event.text()) == 0
                                 or len(completion_prefix) < 2
                                 or event.text()[-1] in end_of_word)):
            c.popup().hide()
            return

        popup = c.popup()
        if completion_prefix != c.completionPrefix():
            c.setCompletionPrefix(completion_prefix)
            popup.setCurrentIndex(c.completionModel().index(0, 0))

        cr = self.cursorRect()
        cr.setWidth(popup.sizeHintForColumn(0)
                    + popup.verticalScrollBar().sizeHint().width())
        c.complete(cr)


class JsonView(QtWidgets.QTreeView):
    def __init__(self, parent=None):
        super(JsonView, self).__init__(parent)
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.on_right_click)

    def on_right_click(self, position):
        index = self.indexAt(position)

        if not index.isValid():
            # Clicked outside any item
            return

        model_ = index.model()
        menu = QtWidgets.QMenu(self)
        copy = QtWidgets.QAction("Copy JSON", menu)
        copy_full = QtWidgets.QAction("Copy full JSON", menu)

        menu.addAction(copy)
        menu.addAction(copy_full)
        menu.addSeparator()

        def on_copy():
            text = str(model_.data(index, JsonModel.JsonRole))
            app = QtWidgets.QApplication.instance()
            app.clipboard().setText(text)

        def on_copy_full():
            if isinstance(model_, QtCore.QSortFilterProxyModel):
                data = model_.sourceModel().json()
            else:
                data = model_.json()

            text = json.dumps(data,
                              indent=4,
                              sort_keys=True,
                              ensure_ascii=False)

            app = QtWidgets.QApplication.instance()
            app.clipboard().setText(text)

        copy.triggered.connect(on_copy)
        copy_full.triggered.connect(on_copy_full)

        menu.move(QtGui.QCursor.pos())
        menu.show()


class QArgParserDialog(QtWidgets.QDialog):

    def __init__(self, parent=None):
        super(QArgParserDialog, self).__init__(parent=parent)
        self.setObjectName("QArgParserDialog")

        widgets = {
            "accept": QtWidgets.QPushButton("Accept"),
            "reject": QtWidgets.QPushButton("Cancel"),
        }
        widgets["accept"].setObjectName("AcceptButton")
        widgets["reject"].setObjectName("CancelButton")

        widgets["accept"].setDefault(True)

        widgets["accept"].clicked.connect(self.on_accepted)
        widgets["reject"].clicked.connect(self.on_rejected)

        self._widgets = widgets
        self._parsers = []
        self._storage = None

    def install(self, options, storage):
        parsers = qargparse.QArgumentParser(options)
        accepts = self._widgets["accept"]
        rejects = self._widgets["reject"]

        layout = QtWidgets.QGridLayout(self)
        layout.addWidget(parsers, 0, 0, 1, 2)
        layout.addWidget(accepts, 1, 0, 1, 1)
        layout.addWidget(rejects, 1, 1, 1, 1)

        self._parsers = parsers
        self._storage = storage

        try:
            retrieved = self.retrieve()
        except ValueError:
            print("Retrieving save option history failed, use default.")
            self._storage.clear()
        else:
            self.write(retrieved)

    def read(self):
        data = dict()
        for arg in self._parsers:
            data[arg["name"]] = arg.read()

        return data

    def write(self, data):
        for arg in self._parsers:
            key = arg["name"]
            if key in data:
                arg.write(data[key])

    def retrieve(self):
        data = dict()
        for arg in self._parsers:
            key = arg["name"]
            value = self._storage.value(key)
            if value is not None:
                data[key] = self.formatting(arg, value)

        return data

    def store(self):
        for arg in self._parsers:
            self._storage.setValue(arg["name"], arg.read())

    def on_accepted(self):
        self.store()
        self.done(self.Accepted)

    def on_rejected(self):
        self.done(self.Rejected)

    def formatting(self, arg, value):
        if isinstance(arg, qargparse.Boolean):
            value = bool({
                None: QtCore.Qt.Unchecked,

                0: QtCore.Qt.Unchecked,
                1: QtCore.Qt.Checked,
                2: QtCore.Qt.Checked,

                "0": QtCore.Qt.Unchecked,
                "1": QtCore.Qt.Checked,
                "2": QtCore.Qt.Checked,

                # May be stored as string, if used with IniFormat
                "false": QtCore.Qt.Unchecked,
                "true": QtCore.Qt.Checked,
            }.get(value))

        if isinstance(arg, qargparse.Number):
            if isinstance(arg, qargparse.Float):
                value = float(value)
            else:
                value = int(value)

        return value


class SimpleDialog(QtWidgets.QDialog):

    def __init__(self, message, options, parent=None):
        super(SimpleDialog, self).__init__(parent=parent)
        self.setObjectName("SimpleDialog")

        widgets = {
            "message": QtWidgets.QLabel(message),
            "reject": QtWidgets.QPushButton("Cancel"),
        }
        widgets["reject"].setObjectName("CancelButton")

        for opt in options:
            widgets[opt] = QtWidgets.QPushButton(opt.capitalize())
        widgets[options[0]].setDefault(True)

        layout = QtWidgets.QGridLayout(self)
        layout.addWidget(widgets["message"], 0, 0, 1, -1)
        for col, opt in enumerate(options):
            layout.addWidget(widgets[opt], 2, col, 1, 1)
        layout.addWidget(widgets["reject"], 2, col + 1, 1, 1)

        for opt in options:
            widgets[opt].clicked.connect(partial(self.on_accepted, opt))
        widgets["reject"].clicked.connect(self.on_rejected)

        self._widgets = widgets
        self._answer = None

    def on_accepted(self, option):
        self._answer = option
        self.done(self.Accepted)

    def on_rejected(self):
        self.done(self.Rejected)

    def answer(self):
        return self._answer
