
import re
import json
import logging
import traceback
from io import StringIO
from contextlib import contextmanager

from rez.system import system
from rez.resolved_context import ResolvedContext
from rez.utils import colorize

from .. import lib, core
from ._vendor.Qt5 import QtWidgets, QtGui, QtCore
from ._vendor import qoverview
from . import delegates, resources as res
from .models import (
    QSingleton,
    JsonModel,
    ResolvedPackagesModel,
    ResolvedEnvironmentModel,
    ContextToolTreeModelSingleton,
    ContextToolTreeSortProxyModel,
    InstalledPackagesModel,
    InstalledPackagesProxyModel,
    SuiteStorageModel,
    SuiteToolTreeModel,
    CompleterProxyModel,
)


log = logging.getLogger("sweet")


class BusyEventFilterSingleton(QtCore.QObject, metaclass=QSingleton):
    overwhelmed = QtCore.Signal(str)

    def eventFilter(self, watched: QtCore.QObject, event: QtCore.QEvent) -> bool:
        if event.type() in (
            QtCore.QEvent.Scroll,
            QtCore.QEvent.KeyPress,
            QtCore.QEvent.KeyRelease,
            QtCore.QEvent.MouseButtonPress,
            QtCore.QEvent.MouseButtonRelease,
            QtCore.QEvent.MouseButtonDblClick,
        ):
            self.overwhelmed.emit("Not allowed at this moment.")
            return True
        return False


class BusyWidget(QtWidgets.QWidget):
    """
    Instead of toggling QWidget.setEnabled() to block user inputs and makes
    the appearance looks glitchy between short time processes, install an
    eventFilter to block keyboard and mouse events plus a busy cursor looks
    better.
    """
    _instances = []

    def __init__(self, *args, **kwargs):
        super(BusyWidget, self).__init__(*args, **kwargs)
        self._is_busy = False
        self._entered = False
        self._filter = BusyEventFilterSingleton(self)
        self._instances.append(self)

    @classmethod
    def instances(cls):
        return cls._instances[:]

    @QtCore.Slot(bool)  # noqa
    def set_overwhelmed(self, busy):
        if self._is_busy == busy:
            return
        self._is_busy = busy
        if self._entered:
            self._over_busy_cursor(busy)
        self._block_children(busy)

    def enterEvent(self, event):
        if self._is_busy:
            self._over_busy_cursor(True)
        self._entered = True
        super(BusyWidget, self).enterEvent(event)

    def leaveEvent(self, event):
        if self._is_busy:
            self._over_busy_cursor(False)
        self._entered = False
        super(BusyWidget, self).leaveEvent(event)

    def _over_busy_cursor(self, over):
        if over:
            QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.BusyCursor)
        else:
            QtWidgets.QApplication.restoreOverrideCursor()

    def _block_children(self, block):

        def action(w):
            if block:
                w.installEventFilter(self._filter)
            else:
                w.removeEventFilter(self._filter)

        def iter_children(w):
            for c in w.children():
                yield c
                for gc in iter_children(c):
                    yield gc

        for child in list(iter_children(self)):
            action(child)
        action(self)


class DragDropListWidget(QtWidgets.QListWidget):
    dropped = QtCore.Signal()

    def __init__(self, *args, **kwargs):
        super(DragDropListWidget, self).__init__(*args, **kwargs)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(self.InternalMove)
        self.setDefaultDropAction(QtCore.Qt.MoveAction)

    def dropEvent(self, event):
        # type: (QtGui.QDropEvent) -> None
        super(DragDropListWidget, self).dropEvent(event)
        if event.isAccepted():
            self.dropped.emit()


class TreeView(qoverview.VerticalExtendedTreeView):

    def __init__(self, *args, **kwargs):
        super(TreeView, self).__init__(*args, **kwargs)
        self.setAllColumnsShowFocus(True)
        self.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.setStyleSheet("""
            QTreeView::item{
                padding: 5px 1px;
                border: 0px;
            }
        """)


class JsonView(TreeView):

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


class MessageDialog(QtWidgets.QDialog):

    def __init__(self, message, title=None, level=None, *args, **kwargs):
        super(MessageDialog, self).__init__(*args, **kwargs)

        level = logging.INFO if level is None else level

        title = title or {
            logging.INFO: "Info",
            logging.WARNING: "Warning",
            logging.ERROR: "Error",
            logging.CRITICAL: "Critical Error",
        }.get(level, "Oops ?")

        icon_name = {
            logging.INFO: "LogInfoIcon",
            logging.WARNING: "LogWarningIcon",
            logging.ERROR: "LogErrorIcon",
            logging.CRITICAL: "LogCriticalIcon",
        }.get(level, "LogUndefinedIcon")

        self.setWindowTitle(title)

        icon = QtWidgets.QLabel()
        icon.setObjectName(icon_name)

        label = QtWidgets.QLabel()
        label.setObjectName("LogLevelText")
        label.setText(title)

        text = QtWidgets.QPlainTextEdit()
        text.setObjectName("LogMessageText")
        text.setPlainText(message)
        text.setLineWrapMode(text.NoWrap)
        text.setReadOnly(True)

        btn_dismiss = QtWidgets.QPushButton("Dismiss")
        btn_dismiss.setDefault(True)

        _layout = QtWidgets.QHBoxLayout()
        _layout.addWidget(icon)
        _layout.addWidget(label, stretch=True)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(_layout)
        layout.addWidget(text)
        layout.addWidget(btn_dismiss)

        btn_dismiss.clicked.connect(lambda: self.done(self.Accepted))


class YesNoDialog(QtWidgets.QDialog):
    """An Accept/Cancel modal dialog for wrapping custom widget

    If widget has signal 'validated', it will be connected with Accept
    button's `setEnabled()` slot to block invalid input.

    """

    def __init__(self, widget, yes_as_default=True, *args, **kwargs):
        super(YesNoDialog, self).__init__(*args, **kwargs)

        btn_accept = QtWidgets.QPushButton("Accept")
        btn_reject = QtWidgets.QPushButton("Cancel")

        btn_accept.setObjectName("AcceptButton")
        btn_reject.setObjectName("CancelButton")
        btn_accept.setDefault(yes_as_default)
        btn_reject.setDefault(not yes_as_default)

        layout = QtWidgets.QGridLayout(self)
        layout.addWidget(widget, 0, 0, 1, 2)
        layout.addWidget(btn_accept, 1, 0, 1, 1)
        layout.addWidget(btn_reject, 1, 1, 1, 1)

        btn_accept.clicked.connect(lambda: self.done(self.Accepted))
        btn_reject.clicked.connect(lambda: self.done(self.Rejected))
        if hasattr(widget, "validated"):
            widget.validated.connect(btn_accept.setEnabled)
            btn_accept.setEnabled(False)


class SuiteHeadWidget(QtWidgets.QWidget):
    branch_asked = QtCore.Signal()
    savable_asked = QtCore.Signal()
    dirty_asked = QtCore.Signal()
    new_clicked = QtCore.Signal()
    save_clicked = QtCore.Signal(str, str, str)

    def __init__(self, details, *args, **kwargs):
        super(SuiteHeadWidget, self).__init__(*args, **kwargs)
        self.setObjectName("SuiteHeadWidget")

        label = QtWidgets.QLabel()
        label.setObjectName("SuiteNameEditIcon")

        name = ValidNameLineEdit()
        new_btn = QtWidgets.QPushButton(" New")
        save_btn = QtWidgets.QPushButton(" Save")

        name.setObjectName("SuiteNameEdit")
        new_btn.setObjectName("SuiteNewButton")
        save_btn.setObjectName("SuiteSaveButton")

        save_btn.setEnabled(False)
        name.setPlaceholderText("Suite name..")

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 0)
        layout.addWidget(label)
        layout.addWidget(name)
        layout.addWidget(save_btn)
        layout.addWidget(new_btn)

        name.textChanged.connect(lambda t: save_btn.setEnabled(bool(t)))
        new_btn.clicked.connect(self.on_suite_new_clicked)
        save_btn.clicked.connect(self.on_suite_save_clicked)

        self._name = name
        self._desc = details.description
        self._path = details.load_path
        self._loaded_branch = None
        # fields for asking
        self._dirty = None
        self._unsavable = None
        self._branches = None

    @QtCore.Slot()  # noqa
    def on_suite_newed(self):
        self._name.setText("")
        self._desc.setPlainText("")
        self._path.setText("")
        self._loaded_branch = None

    @QtCore.Slot(core.SavedSuite)  # noqa
    def on_suite_saved(self, saved_suite):
        self._path.setText(saved_suite.path)

    @QtCore.Slot(str)  # noqa
    def on_suite_save_failed(self, err_message):
        dialog = MessageDialog(err_message,
                               title="Failed Saving Suite",
                               level=logging.CRITICAL,
                               parent=self)
        dialog.open()

    @QtCore.Slot(str, str, str, str)  # noqa
    def on_suite_loaded(self, name, description, load_path, branch):
        is_import = load_path == ""
        self._name.setText(name)
        self._desc.setPlainText(description)
        self._path.setText(load_path)
        self._loaded_branch = None if is_import else branch

    def answer_branches(self, result):
        self._branches = result

    def answer_dirty(self, value):
        self._dirty = value

    def answer_savable(self, objection):
        self._unsavable = objection

    def on_suite_new_clicked(self):
        self._dirty = None
        self.dirty_asked.emit()
        assert self._dirty is not None  # todo: prompt error to status bar

        if self._dirty:
            widget = QtWidgets.QLabel(
                "Current suite is not saved, are you sure to discard and start "
                "a new one ?"
            )
            dialog = YesNoDialog(widget, yes_as_default=False, parent=self)
            dialog.setWindowTitle("Unsaved Changes")

            def on_finished(result):
                if result:
                    self.new_clicked.emit()

            dialog.finished.connect(on_finished)
            dialog.open()

        else:
            self.new_clicked.emit()

    def on_suite_save_clicked(self):
        self._unsavable = None
        self.savable_asked.emit()
        if self._unsavable:
            dialog = MessageDialog(self._unsavable,
                                   title="Cannot Save Suite",
                                   level=logging.WARNING,
                                   parent=self)
            dialog.open()
            return

        self._branches = None
        self.branch_asked.emit()
        assert self._branches is not None  # todo: prompt error to status bar
        assert self._loaded_branch is None \
               or self._loaded_branch in self._branches

        widget = QtWidgets.QWidget()
        hint = QtWidgets.QLabel("Where to save this suite ?")
        box = QtWidgets.QComboBox()
        box.addItems(self._branches)
        layout = QtWidgets.QVBoxLayout(widget)
        layout.addWidget(hint)
        layout.addWidget(box)

        if self._loaded_branch:
            box.setCurrentText(self._loaded_branch)

        dialog = YesNoDialog(widget, parent=self)
        dialog.setWindowTitle("Save Suite")

        def on_finished(result):
            if result:
                branch = box.currentText()
                name = self._name.text()
                description = self._desc.toPlainText()
                self.save_clicked.emit(branch, name, description)

        dialog.finished.connect(on_finished)
        dialog.open()


class SuiteDetailsWidget(QtWidgets.QWidget):

    def __init__(self, *args, **kwargs):
        super(SuiteDetailsWidget, self).__init__(*args, **kwargs)
        self.setObjectName("SuiteDetailsWidget")

        description = QtWidgets.QTextEdit()
        load_path = QtWidgets.QLineEdit()

        description.setPlaceholderText("description..")
        load_path.setPlaceholderText(" load path.. (read-only)")
        load_path.setReadOnly(True)

        description.setMinimumHeight(40)  # for shrinking with splitter

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.addWidget(description, stretch=True)
        layout.addWidget(load_path)
        layout.addSpacing(8)

        self.description = description
        self.load_path = load_path


class ContextDragDropList(DragDropListWidget):

    def __init__(self, *args, **kwargs):
        super(ContextDragDropList, self).__init__(*args, **kwargs)
        self.setSortingEnabled(False)  # do not sort this !
        self.setSelectionMode(self.SingleSelection)
        self.setStyleSheet("""
            QListWidget::item{
                padding: 5px 1px;
                border: 0px;
            }
        """)

    def mouseReleaseEvent(self, event):
        # type: (QtGui.QMouseEvent) -> None
        super(ContextDragDropList, self).mouseReleaseEvent(event)
        # disable item deselecting
        #   we need the selection as on indicator for knowing which context
        #   other widgets are representing.
        item = self.itemAt(event.pos())
        if item and item == self.currentItem():
            item.setSelected(True)


class ContextListWidget(QtWidgets.QWidget):
    added = QtCore.Signal(str)
    renamed = QtCore.Signal(str, str)
    dropped = QtCore.Signal(str)
    reordered = QtCore.Signal(list)
    selected = QtCore.Signal(str)

    def __init__(self, *args, **kwargs):
        super(ContextListWidget, self).__init__(*args, **kwargs)
        self.setObjectName("ContextListWidget")

        label = QtWidgets.QLabel("Context Stack")

        view = ContextDragDropList()

        btn_add = QtWidgets.QPushButton("Add")
        btn_add.setObjectName("ContextAddOpBtn")

        btn_rm = QtWidgets.QPushButton("Remove")
        btn_rm.setObjectName("ContextRemoveOpBtn")

        # layout

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(label)
        layout.addWidget(btn_add)
        layout.addWidget(view, stretch=True)
        layout.addWidget(btn_rm)

        # signals

        btn_add.clicked.connect(self.add_context)
        btn_rm.clicked.connect(self.drop_context)
        view.currentTextChanged.connect(self.selected)
        view.dropped.connect(self.context_reordered)
        view.itemDoubleClicked.connect(self.rename_context)

        self._view = view
        self._icon_ctx = QtGui.QIcon(":/icons/layers-half.svg")
        self._icon_ctx_f = QtGui.QIcon(":/icons/exclamation-triangle-fill.svg")

    def on_request_edited(self, name, edited):
        font = QtGui.QFont()
        font.setBold(edited)
        item = self._find_item(name)  # type: QtWidgets.QListWidgetItem
        item.setFont(font)

    def on_context_resolved(self, name, context):
        icon = self._icon_ctx if context.success else self._icon_ctx_f
        item = self._find_item(name)  # type: QtWidgets.QListWidgetItem
        item.setIcon(icon)

    def on_context_added(self, ctx):
        item = QtWidgets.QListWidgetItem(ctx.name)
        item.setIcon(self._icon_ctx)
        self._view.insertItem(0, item)
        self._view.setCurrentRow(0)

    def on_context_dropped(self, name):
        item = self._find_item(name)
        assert item is not None, f"{name!r} not exists, this is a bug."
        self._view.takeItem(self._view.row(item))
        self._view.removeItemWidget(item)

    def on_context_reordered(self, new_order):
        dragged = self._view.currentItem().text()
        dropped_in = new_order.index(dragged)

        items = []
        for name in new_order:
            item = self._find_item(name)
            if item is None:  # may happen when the item being dragged is the
                continue      # only item in list.
            self._view.takeItem(self._view.row(item))
            items.append(item)

        for item in items:
            self._view.addItem(item)

        self._view.setCurrentRow(dropped_in)

    def on_context_renamed(self, name, new_name):
        item = self._find_item(name)
        assert item is not None, f"{name!r} not exists, this is a bug."
        item.setText(new_name)

    def on_suite_newed(self):
        self._view.clear()

    def _find_item(self, name):
        match_flags = QtCore.Qt.MatchExactly
        return next(iter(self._view.findItems(name, match_flags)), None)

    def add_context(self):
        existing = self.context_names()
        widget = ContextNameEditWidget(existing=existing)
        dialog = YesNoDialog(widget, parent=self)
        dialog.setWindowTitle("Name New Context")

        def on_finished(result):
            if result:
                self.added.emit(widget.get_name())

        dialog.finished.connect(on_finished)
        dialog.open()

    def rename_context(self, item):
        """
        :param item:
        :type item: QtWidgets.QListWidgetItem
        :return:
        """
        old_name = item.text()
        existing = self.context_names()
        existing.remove(old_name)

        widget = ContextNameEditWidget(existing=existing, default=old_name)
        dialog = YesNoDialog(widget, parent=self)
        dialog.setWindowTitle("Rename Context")

        def on_finished(result):
            if result:
                new_name = widget.get_name()
                if old_name != new_name:
                    self.renamed.emit(old_name, new_name)

        dialog.finished.connect(on_finished)
        dialog.open()

    def drop_context(self):
        names = self.selected_contexts()
        for name in names:
            self.dropped.emit(name)

    def selected_contexts(self):
        return [
            item.text() for item in self._view.selectedItems()
        ]

    def context_names(self):
        return [
            self._view.item(row).text()
            for row in range(self._view.count())
        ]

    def context_reordered(self):
        new_order = self.context_names()
        self.reordered.emit(new_order)


class ValidNameLineEdit(QtWidgets.QLineEdit):
    blacked = QtCore.Signal()
    prompted = QtCore.Signal(str)
    validated = QtCore.Signal(bool)

    def __init__(self, blacklist=None, default="", *args, **kwargs):
        super(ValidNameLineEdit, self).__init__(*args, **kwargs)

        interval = 1000
        blacklist = blacklist or []

        validator = RegExpValidator("^[a-zA-Z0-9_.-]*$")
        self.setText(default)
        self.setValidator(validator)
        self.setToolTip("Only alphanumeric characters A-Z, a-z, 0-9 and "
                        "_, -, . are allowed.")

        timer = QtCore.QTimer(self)
        timer.setSingleShot(True)
        timer.setInterval(interval)

        anim = QtCore.QPropertyAnimation()
        anim.setEasingCurve(QtCore.QEasingCurve.InCubic)
        anim.setDuration(interval)

        anim.finished.connect(self._on_anim_finished)
        timer.timeout.connect(lambda: self.prompted.emit(""))
        validator.validated.connect(self._on_validator_validated)
        self.textChanged.connect(self._on_changed_check_blacklist)

        self._anim = anim
        self._timer = timer
        self._color = None
        self._interval = interval
        self._blacklist = blacklist
        self.__block = False

        anim.setTargetObject(self)
        anim.setPropertyName(QtCore.QByteArray(b"_qproperty_color"))
        # disabling yes-no-dialog's accept button on launch if no default
        self.validated.emit(bool(default))

    def _on_validator_validated(self, state):
        if state == QtGui.QValidator.Invalid:
            self.prompted.emit("Invalid char.")
            self._anim.stop()
            self._setup_anim_colors()
            self._anim.start()
            self._timer.start()

    def _on_anim_finished(self):
        self._blacked_hint(self.text() in self._blacklist)

    def _on_changed_check_blacklist(self, value):
        is_blacked = value in self._blacklist
        self._blacked_hint(is_blacked)
        self.validated.emit(not is_blacked and bool(value))

    def _blacked_hint(self, show):
        self._setup_anim_colors()
        self._anim.start()
        self._anim.pause()
        if show:
            self.blacked.emit()
            self._anim.setCurrentTime(0)
        else:
            self.prompted.emit("")
            self._anim.setCurrentTime(self._interval - 1)
            # finished signal emitted when the current time equals to
            # totalDuration (interval).

    def _setup_anim_colors(self):
        theme = res.current_theme()
        color_invalid = theme.palette.error.q_color()
        color_ready = theme.palette.border.q_color()
        self._anim.setStartValue(color_invalid)
        self._anim.setEndValue(color_ready)
        self._color = color_ready

    def _get_color(self):
        return self._color or QtGui.QColor()

    def _set_color(self, color):
        self._color = color
        self.setStyleSheet("border-color: %s;" % color.name())

    _qproperty_color = QtCore.Property(QtGui.QColor, _get_color, _set_color)

    def changeEvent(self, event):
        super(ValidNameLineEdit, self).changeEvent(event)
        if not self.__block and event.type() == QtCore.QEvent.StyleChange:
            # update color when theme changed (blockSignals not working here)
            self.__block = True
            self._setup_anim_colors()
            self.__block = False


class ContextNameEditWidget(QtWidgets.QWidget):
    validated = QtCore.Signal(bool)

    def __init__(self, existing, default="", *args, **kwargs):
        super(ContextNameEditWidget, self).__init__(*args, **kwargs)
        self.setMinimumWidth(300)

        name = ValidNameLineEdit(blacklist=existing, default=default)
        name.setPlaceholderText("Input context name..")
        message = QtWidgets.QLabel()

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(name)
        layout.addWidget(message)

        name.prompted.connect(message.setText)
        name.blacked.connect(lambda: message.setText("Duplicated Name."))
        name.validated.connect(self.validated)
        name.textChanged.connect(self._on_text_changed)

        self._name = ""
        self._message = message

    def _on_text_changed(self, text):
        self._name = text

    def get_name(self):
        return self._name


class RegExpValidator(QtGui.QRegExpValidator):
    validated = QtCore.Signal(QtGui.QValidator.State)

    def __init__(self, pattern):
        super(RegExpValidator, self).__init__(QtCore.QRegExp(pattern))
        self._pattern = re.compile(pattern)

    def validate(self, text, pos):
        state, t, c = super(RegExpValidator, self).validate(text, pos)
        self.validated.emit(state)
        return state, t, c


class ToolsView(TreeView):
    alias_changed = QtCore.Signal(str, str, str)
    hide_changed = QtCore.Signal(str, str, bool)

    def __init__(self, *args, **kwargs):
        super(ToolsView, self).__init__(*args, **kwargs)
        self.setObjectName("ToolsView")


class ContextToolTreeWidget(QtWidgets.QWidget):

    def __init__(self, *args, **kwargs):
        super(ContextToolTreeWidget, self).__init__(*args, **kwargs)
        self.setObjectName("ToolStack")

        label = QtWidgets.QLabel("Tool Stack")

        view = ToolsView()
        model = ContextToolTreeModelSingleton()
        proxy = ContextToolTreeSortProxyModel()

        proxy.setSourceModel(model)
        view.setModel(proxy)
        view.setSortingEnabled(True)

        header = view.header()
        header.setSortIndicatorShown(False)
        header.setSectionResizeMode(0, header.ResizeToContents)

        # layout

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(label)
        layout.addWidget(view)

        # signals
        model.require_expanded.connect(self._on_model_require_expanded)

        self._view = view
        self._proxy = proxy
        self._model = model

    def model(self):
        return self._model

    def _on_model_require_expanded(self, indexes):
        for index in indexes:
            self._view.expand(self._proxy.mapFromSource(index))


class NameStackedBase(QtWidgets.QStackedWidget):
    """Base widget class for stacking named context widgets

    Widgets within this stack will be added/removed/renamed by context
    operations.

    """

    def __init__(self, *args, **kwargs):
        super(NameStackedBase, self).__init__(*args, **kwargs)
        self._names = []
        self._callbacks = []  # type: list[dict["op_name", "callback"]]
        self._add_panel_0()

    def create_panel(self):
        """Re-implement this method for widget creation
        :return: A widget to be stacked
        :rtype: QtWidgets.QWidget
        """
        raise NotImplementedError

    def _add_panel_0(self):
        op_name = ":added:"
        panel = self.add_panel(enabled=False)
        callback = getattr(panel, "callbacks", {}).get(op_name)
        if callable(callback):
            _self = panel
            ctx = ""
            callback(_self, ctx)

    def add_panel(self, enabled=True):
        """Push a new panel widget into stack
        """
        panel = self.create_panel()
        panel.setEnabled(enabled)
        self.insertWidget(0, panel)
        return panel

    def run_panel_callback(self, index, op_name, *args, **kwargs):
        callback = self._callbacks[index].get(op_name)
        if callable(callback):
            _self = self.widget(index)  # get instance from correct thread
            callback(_self, *args, **kwargs)

    @QtCore.Slot(core.SuiteCtx)  # noqa
    def on_context_added(self, ctx):
        op_name = ":added:"
        is_first = len(self._names) == 0
        if is_first:
            panel = self.widget(0)
            panel.setEnabled(True)
            panel.setStyleSheet(panel.styleSheet())
            # note:
            #   Re-applying stylesheet for correcting the color of placeholder
            #   text in QLineEdit. Somehow the placeholder text gets brighter
            #   color when the widget is re-enabled, but this only happens on
            #   MacOS, and only the QLineEdit in the first panel and, when the
            #   stylesheet is applied. This also happens with PyQt5.
        else:
            panel = self.add_panel()
            self.setCurrentIndex(0)

        self._names.insert(0, ctx.name)
        self._callbacks.insert(0, getattr(panel, "callbacks", {}))
        self.run_panel_callback(0, op_name, ctx)

    @QtCore.Slot(str, object)  # noqa
    def on_context_resolved(self, name, context):
        """

        :param name:
        :param context:
        :type name: str
        :type context: ResolvedContext or core.BrokenContext
        :return:
        """
        op_name = ":resolved:"
        index = self._names.index(name)
        self.run_panel_callback(index, op_name, context)

    @QtCore.Slot(str, str)  # noqa
    def on_context_renamed(self, name, new_name):
        op_name = ":renamed:"
        index = self._names.index(name)
        self.run_panel_callback(index, op_name, new_name)

        self._names.remove(name)
        self._names.insert(index, new_name)

    @QtCore.Slot(str)  # noqa
    def on_context_dropped(self, name):
        index = self._names.index(name)
        self._callbacks.pop(index)
        self._names.remove(name)
        is_empty = len(self._names) == 0

        panel = self.widget(index)
        self.removeWidget(panel)
        if is_empty:
            self._add_panel_0()

    @QtCore.Slot(str)  # noqa
    def on_context_selected(self, name):
        # name may not exists yet while the context is just being added.
        if name in self._names:
            self.setCurrentIndex(self._names.index(name))

    @QtCore.Slot()  # noqa
    def on_suite_newed(self):
        self._callbacks.clear()
        for i in range(self.count()):
            self.removeWidget(self.widget(0))
        self._names.clear()
        self._add_panel_0()


class StackedResolveWidget(NameStackedBase):

    def create_panel(self):
        panel = ContextResolveWidget()
        return panel


class StackedRequestWidget(NameStackedBase):
    requested = QtCore.Signal(str, list)
    request_edited = QtCore.Signal(str, bool)
    prefix_changed = QtCore.Signal(str, str)
    suffix_changed = QtCore.Signal(str, str)

    def create_panel(self):
        panel = ContextRequestWidget()
        panel.prefix_changed.connect(
            lambda text: self.prefix_changed.emit(panel.name(), text)
        )
        panel.suffix_changed.connect(
            lambda text: self.suffix_changed.emit(panel.name(), text)
        )
        panel.requested.connect(
            lambda requests: self.requested.emit(panel.name(), requests)
        )
        panel.request_edited.connect(
            lambda edited: self.request_edited.emit(panel.name(), edited)
        )
        return panel


class RequestTableItemDelegate(QtWidgets.QStyledItemDelegate):

    def createEditor(self, parent, option, index):
        """
        :type parent: QtWidgets.QWidget
        :type option: QtWidgets.QStyleOptionViewItem
        :type index: QtCore.QModelIndex
        :rtype: QtWidgets.QWidget or None
        """
        if not index.isValid():
            return
        if index.column() == 0:
            editor = QtWidgets.QLineEdit(parent)
            editor.setPlaceholderText("add one request..")
            editor.setObjectName("RequestTextEdit")

            completer = RequestCompleter(editor)
            completer.setPopup(CompleterPopup())
            # The completion role leave it as default (Qt.EditRole), because
            # unlike the completer in the RequestTextEdit widget, QLineEdit
            # works better with full completion replacement.

            editor.setCompleter(completer)

            return editor


class RequestTableEdit(QtWidgets.QTableWidget):
    edited = QtCore.Signal()

    def __init__(self, *args, **kwargs):
        super(RequestTableEdit, self).__init__(*args, **kwargs)
        self.setObjectName("RequestTableEdit")

        delegate = RequestTableItemDelegate(self)

        self.setRowCount(1)
        self.setColumnCount(1)
        self.horizontalHeader().setStretchLastSection(True)
        self.horizontalHeader().setVisible(False)
        self.verticalHeader().setVisible(False)
        self.setShowGrid(True)
        self.setEditTriggers(self.AllEditTriggers)
        self.setItemDelegate(delegate)

        self.itemChanged.connect(self.on_item_changed)

    def on_item_changed(self, item):
        if item.row() < self.rowCount() - 1:
            if not item.text():
                self.removeRow(item.row())
        self.edited.emit()

    def open_editor(self, row):
        if row < 0:
            return
        self.openPersistentEditor(self.item(row, 0))
        editor = self.cellWidget(row, 0)  # type: QtWidgets.QLineEdit

        def on_editing_finished():
            _row = self.currentRow()
            text = editor.text()
            if text:
                editor.editingFinished.disconnect(on_editing_finished)
                self.process_row_edited(text, _row)
                self.closePersistentEditor(self.item(_row, 0))

        editor.editingFinished.connect(on_editing_finished)
        self.setCurrentCell(row, 0)

    def process_row_edited(self, text, row):
        if row == self.rowCount() - 1:
            if text:
                row += 1
                self.insertRow(row)
                self.setItem(row, 0, QtWidgets.QTableWidgetItem())
                self.open_editor(row)
                self.cellWidget(row - 1, 0).setFocus()  # grab focus on Tab key
        else:
            if not text:
                self.removeRow(row)

    def replace_requests(self, requests):
        self.remove_all_rows()

        for row, text in enumerate(requests):
            self.insertRow(row)
            self.setItem(row, 0, QtWidgets.QTableWidgetItem(text))

        row = self.rowCount()
        self.insertRow(row)
        self.setItem(row, 0, QtWidgets.QTableWidgetItem())
        self.open_editor(row)

    def fetch_requests(self):
        """Get requests from table

        This also collects inputs from active cell widget (inputs that are not
        yet committed into table).

        :return: list of package request string
        :rtype: list[str]
        """
        requests = []
        for row in range(self.rowCount()):
            editor = self.cellWidget(row, 0)
            item = self.item(row, 0)
            if editor is not None:
                text = editor.text()
            elif item is not None:
                text = item.text()
            else:
                text = None

            if text:
                requests.append(text)

        return requests

    def remove_all_rows(self):
        self.clearContents()
        for _ in range(self.rowCount()):
            self.removeRow(0)
        self.setRowCount(0)


class RequestTextEdit(QtWidgets.QTextEdit):
    edited = QtCore.Signal()

    def __init__(self, *args, **kwargs):
        super(RequestTextEdit, self).__init__(*args, **kwargs)
        self.setObjectName("RequestTextEdit")
        self.setPlaceholderText("multi-line requests, e.g.\nfoo\nbar-2.1\n..")
        self.setAcceptRichText(False)
        self.setTabChangesFocus(True)

        # Reference for custom completer in TextEdit:
        #   https://doc.qt.io/qt-5/qtwidgets-tools-customcompleter-example.html
        self._completer = None
        completer = RequestCompleter(self)
        self.setCompleter(completer)

        self.textChanged.connect(self.edited.emit)

    def setCompleter(self, c):
        """
        :param c: The completer
        :type c: QtWidgets.QCompleter
        :return:
        """
        if self._completer is not None:
            self._completer.activated.disconnect()

        self._completer = c

        c.setWidget(self)
        c.setPopup(CompleterPopup())
        c.setCompletionRole(InstalledPackagesModel.CompletionRole)
        # note: this completion role *appends* the completion to the end
        #   of text (see insert_completion()), and is a better suit for
        #   QTextEdit based widget.
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

        if extra != 0:
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
            # popup.setCurrentIndex(c.completionModel().index(0, 0))
            # note: commenting this out as we don't want any selected by
            #   default until we actually picked one from the list.

        cr = self.cursorRect()
        cr.setWidth(popup.sizeHintForColumn(0)
                    + popup.verticalScrollBar().sizeHint().width())
        c.complete(cr)


class RequestEditorWidget(QtWidgets.QWidget):
    edited = QtCore.Signal(bool)

    def __init__(self, *args, **kwargs):
        super(RequestEditorWidget, self).__init__(*args, **kwargs)

        buttons = QtWidgets.QWidget()
        buttons.setObjectName("ButtonBelt")

        table_btn = QtWidgets.QPushButton()
        table_btn.setObjectName("RequestTableBtn")
        table_btn.setCheckable(True)
        table_btn.setChecked(True)  # the default
        text_btn = QtWidgets.QPushButton()
        text_btn.setObjectName("RequestTextBtn")
        text_btn.setCheckable(True)

        stack = QtWidgets.QStackedWidget()
        table_editor = RequestTableEdit()
        text_editor = RequestTextEdit()

        stack.addWidget(table_editor)
        stack.addWidget(text_editor)

        layout = QtWidgets.QHBoxLayout(buttons)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(QtCore.Qt.AlignLeft)
        layout.setSpacing(0)
        layout.addWidget(table_btn)
        layout.addWidget(text_btn, stretch=True)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.addWidget(buttons)
        layout.addWidget(stack)

        def switched(to_index):
            stack.setCurrentIndex(to_index)
            table_btn.setChecked(to_index == 0)
            text_btn.setChecked(to_index == 1)

        table_btn.clicked.connect(lambda: switched(0))
        text_btn.clicked.connect(lambda: switched(1))
        stack.currentChanged.connect(self.on_tab_changed)
        table_editor.edited.connect(self.on_edited)
        text_editor.edited.connect(self.on_edited)

        timer = QtCore.QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(self._deferred_edited)

        self._stack = stack
        self._text = text_editor
        self._table = table_editor
        self._timer = timer
        self._processed = None

    def on_tab_changed(self, index):
        if index == 0:
            # text -> table
            requests = self._text.toPlainText().split()
            self._table.replace_requests(requests)
        elif index == 1:
            # table -> text
            requests = self._table.fetch_requests()
            self._text.setPlainText("\n".join(requests))
            self._table.remove_all_rows()

    def on_edited(self):
        self._timer.start(500)

    def _deferred_edited(self):
        edited = (self._processed or []) != self.get_requests()
        self.edited.emit(edited)

    def set_requests(self, requests):
        index = self._stack.currentIndex()
        if index == 0:
            self._table.replace_requests(list(map(str, requests)))
        elif index == 1:
            self._text.setPlainText("\n".join(map(str, requests)))

    def get_requests(self):
        index = self._stack.currentIndex()
        if index == 0:
            return self._table.fetch_requests()
        elif index == 1:
            return self._text.toPlainText().split()

    def log_processed(self, requests):
        """
        :param list[str] requests:
        """
        self._processed = requests
        self.edited.emit(False)


class ContextRequestWidget(QtWidgets.QWidget):
    requested = QtCore.Signal(list)
    request_edited = QtCore.Signal(bool)
    prefix_changed = QtCore.Signal(str)
    suffix_changed = QtCore.Signal(str)

    def __init__(self, *args, **kwargs):
        super(ContextRequestWidget, self).__init__(*args, **kwargs)

        naming = QtWidgets.QWidget()
        prefix_label = QtWidgets.QLabel("prefix:")
        prefix = QtWidgets.QLineEdit()
        prefix.setPlaceholderText("context prefix..")
        suffix_label = QtWidgets.QLabel("suffix:")
        suffix = QtWidgets.QLineEdit()
        suffix.setPlaceholderText("context suffix..")

        request = RequestEditorWidget()

        resolve = QtWidgets.QPushButton("Resolve")
        resolve.setObjectName("ContextResolveOpBtn")

        layout = QtWidgets.QGridLayout(naming)
        layout.addWidget(prefix_label, 0, 0)
        layout.addWidget(prefix, 0, 1)
        layout.addWidget(suffix_label, 1, 0)
        layout.addWidget(suffix, 1, 1)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(naming)
        layout.addWidget(request)
        layout.addWidget(resolve)

        # signal
        prefix.textChanged.connect(
            lambda text: self.prefix_changed.emit(text)
        )
        suffix.textChanged.connect(
            lambda text: self.suffix_changed.emit(text)
        )
        resolve.clicked.connect(
            lambda: self.requested.emit(request.get_requests())
        )
        request.edited.connect(self.request_edited.emit)

        self._name = None
        self._prefix = prefix
        self._suffix = suffix
        self._request = request

        # will be called by StackedResolveWidget
        self.callbacks = {
            ":added:": ContextRequestWidget.set_context,
            ":renamed:": ContextRequestWidget.set_context,
            ":resolved:": ContextRequestWidget.set_resolved,
        }

    def name(self):
        return self._name

    def set_context(self, ctx):
        """

        :param ctx:
        :type ctx: core.SuiteCtx or str
        :return:
        """
        if isinstance(ctx, str):
            self._name = ctx
        else:
            self.blockSignals(True)
            self._name = ctx.name
            self._prefix.setText(ctx.prefix)
            self._suffix.setText(ctx.suffix)
            self._request.set_requests(ctx.requests)
            self.blockSignals(False)

    def set_resolved(self, context):
        self._request.log_processed(
            list(map(str, context.requested_packages()))
        )


class ContextResolveWidget(QtWidgets.QWidget):

    def __init__(self, *args, **kwargs):
        super(ContextResolveWidget, self).__init__(*args, **kwargs)

        tools = ResolvedTools()
        packages = ResolvedPackages()
        environ = ResolvedEnvironment()
        code = ResolvedCode()
        graph = ResolvedGraph()
        log = ResolvedLog()

        tabs = QtWidgets.QTabBar()
        stack = QtWidgets.QStackedWidget()
        stack.setObjectName("TabStackWidget")
        tabs.setExpanding(True)
        tabs.setDocumentMode(True)
        # QTabWidget's frame (pane border) will not be rendered if documentMode
        # is enabled, so we make our own with bar + stack with border.
        tabs.addTab("Tools")
        stack.addWidget(tools)
        tabs.addTab("Packages")
        stack.addWidget(packages)
        tabs.addTab("Environ")
        stack.addWidget(environ)
        tabs.addTab("Code")
        stack.addWidget(code)
        tabs.addTab("Graph")
        stack.addWidget(graph)
        tabs.addTab("Log")
        stack.addWidget(log)

        _layout = QtWidgets.QVBoxLayout()
        _layout.setSpacing(0)
        _layout.addWidget(tabs)
        _layout.addWidget(stack)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(_layout)

        tabs.currentChanged.connect(stack.setCurrentIndex)

        self._name = None
        self._tabs = tabs
        self._tools = tools
        self._packages = packages
        self._environ = environ
        self._code = code
        self._graph = graph
        self._log = log

        # will be called by StackedResolveWidget
        self.callbacks = {
            ":added:": ContextResolveWidget.set_context,
            ":renamed:": ContextResolveWidget.set_context,
            ":resolved:": ContextResolveWidget.set_resolved,
        }

    def name(self):
        return self._name

    def set_context(self, ctx):
        """

        :param ctx:
        :type ctx: core.SuiteCtx or str
        :return:
        """
        name = ctx if isinstance(ctx, str) else ctx.name
        self._name = name
        self._tools.set_name(name)

    def set_resolved(self, context):
        """

        :param context:
        :type context: ResolvedContext
        :return:
        """
        if context.success:
            self._packages.model().load(context.resolved_packages)
            self._environ.model().load(context.get_environ())
            self._code.set_shell_code(context.get_shell_code())
        else:
            self._tabs.setCurrentIndex(self._tabs.count() - 1)  # Log widget

        with HtmlPrinter.patch_context_printer():
            stream = StringIO()
            context.print_info(stream,
                               verbosity=2,  # noqa, type hint incorrect
                               source_order=True,
                               show_resolved_uris=True)
            stream.seek(0)
            _sep = "=" * 60
            html = "<br>".join(stream.readlines())
            html = html.replace("\t", "&nbsp;" * 4)
            self._log.append_log(f'<p>{_sep}</p><p>{html}</p>')


class ResolvedTools(QtWidgets.QWidget):

    def __init__(self, *args, **kwargs):
        super(ResolvedTools, self).__init__(*args, **kwargs)

        model = ContextToolTreeModelSingleton()
        view = ToolsView()
        view.setModel(model)

        header = view.header()
        header.setSectionResizeMode(0, header.ResizeToContents)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(view)

        self._view = view
        self._model = model
        self._view_fixed = False

    def set_name(self, ctx_name):
        if ctx_name and not self._view_fixed:
            index = self._model.find_root_index(ctx_name)
            if index is None:
                print("Unable to find context item index from model.")
            else:
                self._view.setRootIndex(index)
                self._view_fixed = True


class ResolvedPackages(QtWidgets.QWidget):

    def __init__(self, *args, **kwargs):
        super(ResolvedPackages, self).__init__(*args, **kwargs)

        model = ResolvedPackagesModel()
        view = TreeView()
        view.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        view.setModel(model)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(view)

        view.customContextMenuRequested.connect(self.on_right_click)

        self._view = view
        self._model = model

    def model(self):
        return self._model

    def on_right_click(self, position):
        view = self._view
        model = self._model
        index = view.indexAt(position)

        if not index.isValid():
            # Clicked outside any item
            return

        menu = QtWidgets.QMenu(view)
        openfile = QtWidgets.QAction("Open file location", menu)
        copyfile = QtWidgets.QAction("Copy file location", menu)

        menu.addAction(openfile)
        menu.addAction(copyfile)

        def on_openfile():
            file_path = model.pkg_path_from_index(index)
            if file_path:
                lib.open_file_location(file_path)
            else:
                print("Not a valid filesystem package.")
                # todo: put this into log/status-bar message

        def on_copyfile():
            file_path = model.pkg_path_from_index(index)
            if file_path:
                clipboard = QtWidgets.QApplication.instance().clipboard()
                clipboard.setText(file_path)
            else:
                print("Not a valid filesystem package.")
                # todo: put this into log/status-bar message

        openfile.triggered.connect(on_openfile)
        copyfile.triggered.connect(on_copyfile)

        menu.move(QtGui.QCursor.pos())
        menu.show()


class ResolvedEnvironment(QtWidgets.QWidget):

    def __init__(self, *args, **kwargs):
        super(ResolvedEnvironment, self).__init__(*args, **kwargs)

        model = ResolvedEnvironmentModel()
        view = JsonView()
        view.setModel(model)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(view)

        self._model = model

    def model(self):
        return self._model


class ResolvedCode(QtWidgets.QWidget):

    def __init__(self, *args, **kwargs):
        super(ResolvedCode, self).__init__(*args, **kwargs)

        text = QtWidgets.QTextEdit()
        text.setPlaceholderText("Context environment shell code..")
        text.setLineWrapMode(text.NoWrap)
        text.setReadOnly(True)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(text)

        self._text = text

    def set_shell_code(self, text):
        comment = "REM " if system.shell == "cmd" else "# "

        pretty = []
        for ln in text.split("\n"):
            # todo: the color should be managed in styling module
            level = "lightgrey" if ln.startswith(comment) else "grey"
            color = "<font color=\"%s\">" % level
            pretty.append("%s%s</font>" % (color, ln.replace(" ", "&nbsp;")))

        self._text.setText("<br>".join(pretty))


class ResolvedGraph(QtWidgets.QWidget):
    pass


class ResolvedLog(QtWidgets.QWidget):

    def __init__(self, *args, **kwargs):
        super(ResolvedLog, self).__init__(*args, **kwargs)

        text = QtWidgets.QPlainTextEdit()
        text.setPlaceholderText("Context resolve details..")
        text.setLineWrapMode(text.NoWrap)
        text.setReadOnly(True)

        clear = QtWidgets.QPushButton("clear")

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 0)
        layout.addWidget(text)
        layout.addWidget(clear)

        clear.clicked.connect(text.clear)

        self._text = text

    def append_log(self, html):
        self._text.appendHtml(html)


class VerticalDocTabBar(QtWidgets.QTabBar):

    def __init__(self, *args, **kwargs):
        super(VerticalDocTabBar, self).__init__(*args, **kwargs)
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


class InstalledPackagesTabBar(VerticalDocTabBar):
    def __init__(self, *args, **kwargs):
        super(InstalledPackagesTabBar, self).__init__(*args, **kwargs)
        self.setObjectName("PackageTabBar")
        self.setMinimumHeight(120)


class InstalledPackagesView(TreeView):

    def __init__(self, *args, **kwargs):
        super(InstalledPackagesView, self).__init__(*args, **kwargs)
        self.setObjectName("PackageTreeView")
        self.setSortingEnabled(True)
        self.setAlternatingRowColors(True)
        self.sortByColumn(0, QtCore.Qt.AscendingOrder)

        time_delegate = delegates.PrettyTimeDelegate()
        self.setItemDelegateForColumn(1, time_delegate)

        self._time_delegate = time_delegate


class InstalledPackagesWidget(QtWidgets.QWidget):
    refreshed = QtCore.Signal()

    def __init__(self, *args, **kwargs):
        super(InstalledPackagesWidget, self).__init__(*args, **kwargs)

        wrap = QtWidgets.QWidget()
        head = QtWidgets.QWidget()
        body = QtWidgets.QWidget()
        body.setObjectName("PackagePage")
        side = QtWidgets.QWidget()
        side.setObjectName("PackageSide")

        refresh = QtWidgets.QPushButton()
        refresh.setObjectName("RefreshButton")
        search = QtWidgets.QLineEdit()
        view = InstalledPackagesView()
        model = InstalledPackagesModel()
        proxy = InstalledPackagesProxyModel()
        tabs = InstalledPackagesTabBar()

        proxy.setSourceModel(model)
        view.setModel(proxy)
        search.setPlaceholderText(" Search by family, version or tool..")

        # layout

        layout = QtWidgets.QHBoxLayout(head)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(refresh)
        layout.addWidget(search)

        layout = QtWidgets.QVBoxLayout(side)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(tabs)
        layout.addStretch(100)
        layout.setSpacing(0)

        layout = QtWidgets.QVBoxLayout(body)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.addWidget(view)

        layout = QtWidgets.QHBoxLayout(wrap)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(side)
        layout.addWidget(body)
        layout.setSpacing(0)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(head)
        layout.addSpacing(6)
        layout.addWidget(wrap)
        layout.setSpacing(0)

        # signals

        header = view.header()
        scroll = view.verticalScrollBar()

        tabs.currentChanged.connect(self.on_tab_clicked)
        search.textChanged.connect(self.on_searched)
        header.sortIndicatorChanged.connect(self.on_sort_changed)
        scroll.valueChanged.connect(self.on_scrolled)
        refresh.clicked.connect(self.on_refresh_released)
        model.modelReset.connect(lambda: self.setEnabled(False))
        model.family_updated.connect(self.on_model_family_updated)

        self._view = view
        self._model = model
        self._proxy = proxy

        self._tabs = tabs
        self._groups = []

    def model(self):
        return self._model

    def proxy(self):
        return self._proxy

    @QtCore.Slot(str)  # noqa
    def on_searched(self, text):
        self._proxy.setFilterRegExp(text)
        self._view.expandAll() if len(text) > 1 else self._view.collapseAll()
        self._view.reset_extension()

    @QtCore.Slot(int)  # noqa
    def on_tab_clicked(self, index):
        group = self._tabs.tabText(index)
        item = self._model.first_item_in_initial(group)
        if item is not None:
            index = item.index()
            index = self._proxy.mapFromSource(index)
            self._view.scroll_at_top(index)

    @QtCore.Slot(int)  # noqa
    def on_scrolled(self, value):
        if not self._tabs.isEnabled():
            return

        index = self._view.top_scrolled_index(value)
        index = self._proxy.mapToSource(index)
        name = self._model.data(index)
        if name:
            group = name[0].upper()
            index = self._groups.index(group)
            self._tabs.blockSignals(True)
            self._tabs.setCurrentIndex(index)
            self._tabs.blockSignals(False)

    @QtCore.Slot(int, QtCore.Qt.SortOrder)  # noqa
    def on_sort_changed(self, index, order):
        is_sort_name = index == 0

        self._tabs.setEnabled(is_sort_name)
        if is_sort_name:
            if len(self._groups) <= 1:
                return

            first, second = self._groups[:2]
            is_ascending = int(first > second)
            if is_ascending == int(order):
                return

            self._groups.reverse()
            for i, group in enumerate(self._groups):
                self._tabs.setTabText(i, group)

    @QtCore.Slot()  # noqa
    def on_model_family_updated(self):
        # regenerate tabs
        tabs = self._tabs
        self._groups.clear()
        for index in range(tabs.count()):
            tabs.removeTab(0)

        for group in self._model.initials():
            self._groups.append(group)
            tabs.addTab(group)

        if not self._groups:
            tabs.addTab("")  # placeholder tab for startup

        # (MacOS) Ensure tab bar *polished* even it's not visible on launch.
        tabs.updateGeometry()
        tabs.setEnabled(True)
        self.setEnabled(True)

    @QtCore.Slot()  # noqa
    def on_refresh_released(self):
        self._tabs.setEnabled(False)
        self.refreshed.emit()


class SuiteBranchWidget(QtWidgets.QWidget):
    suite_selected = QtCore.Signal(core.SavedSuite)
    suite_load_clicked = QtCore.Signal(str, str, bool)

    def __init__(self, *args, **kwargs):
        super(SuiteBranchWidget, self).__init__(*args, **kwargs)

        view = TreeView()
        proxy = QtCore.QSortFilterProxyModel()
        model = SuiteStorageModel()

        proxy.setSourceModel(model)
        view.setModel(proxy)
        view.setSortingEnabled(True)
        view.setSelectionMode(view.SingleSelection)
        view.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(view)

        # signals

        view.selectionModel().currentChanged.connect(self._on_current_changed)
        view.customContextMenuRequested.connect(self._on_right_click)

        self._view = view
        self._model = model

    def model(self):
        return self._model

    def _on_current_changed(self, index):
        saved_suite = index.data(self._model.SavedSuiteRole)
        if saved_suite is None:
            return  # possible root item (the branch)
        self.suite_selected.emit(saved_suite)

    def _on_right_click(self, position):
        index = self._view.indexAt(position)

        if not index.isValid():
            # Clicked outside any item
            return

        saved_suite = index.data(role=self._model.SavedSuiteRole)
        if saved_suite is None:
            return  # right-clicking on the branch

        menu = QtWidgets.QMenu(self._view)
        open_ = QtWidgets.QAction("Open suite (loaded)", menu)
        import_ = QtWidgets.QAction("Open suite (import)", menu)
        explore = QtWidgets.QAction("Show in Explorer", menu)

        def on_open():
            name = saved_suite.name
            branch = saved_suite.branch
            self.suite_load_clicked.emit(name, branch, False)

        def on_import():
            name = saved_suite.name
            branch = saved_suite.branch
            self.suite_load_clicked.emit(name, branch, True)

        def on_explore():
            lib.open_file_location(saved_suite.path)

        open_.triggered.connect(on_open)
        import_.triggered.connect(on_import)
        explore.triggered.connect(on_explore)

        menu.addAction(open_)
        menu.addAction(import_)
        menu.addAction(explore)

        menu.move(QtGui.QCursor.pos())
        menu.show()


class SuiteInsightWidget(QtWidgets.QWidget):

    def __init__(self, *args, **kwargs):
        super(SuiteInsightWidget, self).__init__(*args, **kwargs)

        name = QtWidgets.QLineEdit()
        desc = QtWidgets.QTextEdit()
        view = ToolsView()
        model = SuiteToolTreeModel(editable=False)
        header = view.header()

        # todo: tools are not ordered by contexts

        view.setModel(model)
        header.setSectionResizeMode(0, header.ResizeToContents)
        desc.setReadOnly(True)
        name.setReadOnly(True)
        name.setObjectName("SuiteNameView")

        error = QtWidgets.QWidget()
        icon = QtWidgets.QLabel()
        icon.setObjectName("LogErrorIcon")
        label = QtWidgets.QLabel()
        label.setObjectName("LogLevelText")
        label.setText("Suite Corrupted")
        detail = QtWidgets.QPlainTextEdit()
        detail.setObjectName("LogMessageText")
        detail.setReadOnly(True)
        detail.setLineWrapMode(detail.NoWrap)

        _layout = QtWidgets.QHBoxLayout()
        _layout.addWidget(icon)
        _layout.addWidget(label, stretch=True)

        layout = QtWidgets.QVBoxLayout(error)
        layout.addLayout(_layout)
        layout.addWidget(detail)

        stack = QtWidgets.QStackedWidget()
        stack.setContentsMargins(0, 0, 0, 0)
        stack.addWidget(view)
        stack.addWidget(error)

        splitter = QtWidgets.QSplitter()
        splitter.setOrientation(QtCore.Qt.Vertical)
        splitter.addWidget(desc)
        splitter.addWidget(stack)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 8)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(name)
        layout.addWidget(splitter)

        self._name = name
        self._desc = desc
        self._stack = stack
        self._error = detail
        self._view = view
        self._model = model

    def on_suite_selected(self, saved_suite):
        """

        :param saved_suite:
        :type saved_suite: core.SavedSuite
        :return:
        """
        self._name.setText(saved_suite.name)
        self._desc.setPlainText(saved_suite.description)
        self._stack.setCurrentIndex(0)
        added = self._model.add_suite(saved_suite)
        item = self._model.find_suite(saved_suite)
        self._view.setRootIndex(item.index())

        if added:
            try:
                # todo: this may takes times, timeit
                suite_tools = list(saved_suite.iter_saved_tools())

            except Exception as e:
                error = f"{str(e)}\n\n{traceback.format_exc()}"
                log.error(error)
                self._model.set_bad_suite(item, error)
                self._stack.setCurrentIndex(1)
                self._error.setPlainText(error)

            else:
                self._model.update_tools(suite_tools, suite=saved_suite.name)

        else:
            error = self._model.is_bad_suite(item)
            if error:
                self._stack.setCurrentIndex(1)
                self._error.setPlainText(error)


class RequestCompleter(QtWidgets.QCompleter):

    def __init__(self, *args, **kwargs):
        super(RequestCompleter, self).__init__(*args, **kwargs)

        model = InstalledPackagesModel()
        proxy = CompleterProxyModel()
        proxy.setSourceModel(model)
        self.setModel(proxy)

        self.setCompletionColumn(0)
        self.setCompletionMode(self.PopupCompletion)
        self.setModelSorting(self.CaseInsensitivelySortedModel)
        self.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self.setWrapAround(False)

        self._model = model
        self._proxy = proxy

    def model(self):
        return self._model

    def proxy(self):
        return self._proxy

    def splitPath(self, path):
        # TODO: "==", "+<", "..", ...
        return path.split("-", 1)


class CompleterPopup(QtWidgets.QListView):
    def __init__(self, *args, **kwargs):
        super(CompleterPopup, self).__init__(*args, **kwargs)
        self.setObjectName("CompleterPopup")

    def showEvent(self, event):
        self.setStyleSheet(res.get_style_sheet())
        # this seems to be the only way to apply stylesheet to completer
        # popup.
        super(CompleterPopup, self).showEvent(event)


class HtmlPrinter(colorize.Printer):

    def __init__(self, buf):
        super(HtmlPrinter, self).__init__(buf=buf)
        _html = (lambda m, c: f'<span style="color:{c};">{m}</span>')
        self.colorize = True
        self._html_style = {
            colorize.critical: lambda m: _html(m,  "red"),
            colorize.error: lambda m: _html(m,     "red"),
            colorize.warning: lambda m: _html(m,   "yellow"),
            colorize.info: lambda m: _html(m,      "green"),
            colorize.debug: lambda m: _html(m,     "blue"),
            colorize.heading: lambda m: _html(m,   "white"),
            colorize.local: lambda m: _html(m,     "green"),
            colorize.implicit: lambda m: _html(m,  "cyan"),
            colorize.ephemeral: lambda m: _html(m, "blue"),
            colorize.alias: lambda m: _html(m,     "cyan"),
        }

    def get(self, msg, style=None):
        if style and self.colorize:
            _style = self._html_style.get(style)
            _style = _style or style
            msg = _style(msg)
        return msg

    @classmethod
    @contextmanager
    def patch_context_printer(cls):
        from rez import resolved_context
        _Printer = getattr(resolved_context, "Printer")
        setattr(resolved_context, "Printer", cls)
        yield
        setattr(resolved_context, "Printer", _Printer)
