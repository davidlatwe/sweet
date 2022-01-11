
import re
import os
import json
from .. import util, core, _rezapi as rez
from ._vendor.Qt5 import QtWidgets, QtGui, QtCore
from ._vendor import qoverview
from . import delegates, resources as res
from .completer import RequestTextEdit
from .models import (
    JsonModel,
    ResolvedPackagesModel,
    ResolvedEnvironmentModel,
    ToolStackModel,
    ToolStackSortProxyModel,
    InstalledPackagesModel,
    InstalledPackagesProxyModel,
    SuiteStorageModel,
)


class TreeView(qoverview.VerticalExtendedTreeView):

    def __init__(self, *args, **kwargs):
        super(TreeView, self).__init__(*args, **kwargs)
        self.setAllColumnsShowFocus(True)
        self.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.setStyleSheet("""
            QTreeView::item{
                padding: 5px 1px;
                border: 0px;
            }
        """)


class CurrentSuite(QtWidgets.QWidget):

    def __init__(self, *args, **kwargs):
        super(CurrentSuite, self).__init__(*args, **kwargs)
        self.setObjectName("SuiteView")

        name = QtWidgets.QLineEdit()
        description = QtWidgets.QTextEdit()
        load_path = QtWidgets.QLineEdit()

        name.setPlaceholderText("Suite name..")
        description.setPlaceholderText("Suite description.. (optional)")
        description.setMinimumHeight(5)
        load_path.setReadOnly(True)
        load_path.setMinimumHeight(5)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(name)
        layout.addWidget(description, stretch=True)
        layout.addWidget(load_path)
        layout.addStretch()

        self._min_height = self.minimumSizeHint().height()
        self._hide_on_min = [description, load_path]

    def resizeEvent(self, event):
        h = event.size().height()
        for w in self._hide_on_min:
            w.setVisible(h > self._min_height)
        return super(CurrentSuite, self).resizeEvent(event)


class SuiteSavingDialog(QtWidgets.QDialog):
    pass


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
        rte = super(DragDropListWidget, self).dropEvent(event)
        if event.isAccepted():
            self.dropped.emit()
        return rte


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

        view = DragDropListWidget()
        view.setSortingEnabled(False)  # do not sort this !

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

    def on_context_added(self, ctx):
        item = QtWidgets.QListWidgetItem(ctx.name)
        # item.setData(ctx, role=self._model.ItemRole)
        self._view.insertItem(0, item)
        self._view.setCurrentRow(0)

    def on_context_dropped(self, name):
        item = self._find_item(name)
        self._view.takeItem(self._view.row(item))
        self._view.removeItemWidget(item)

    def on_context_reordered(self, new_order):
        items = []
        for name in new_order:
            item = self._find_item(name)
            self._view.takeItem(self._view.row(item))
            items.append(item)
        for item in items:
            self._view.addItem(item)

    def on_context_renamed(self, name, new_name):
        item = self._find_item(name)
        item.setText(new_name)

    def on_suite_reset(self):
        self._view.clear()

    def _find_item(self, name):
        return next(iter(self._view.findItems(name, QtCore.Qt.MatchExactly)))

    def add_context(self):
        existing = self.context_names()
        widget = ContextNameEditor(existing=existing)
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

        widget = ContextNameEditor(existing=existing, default=old_name)
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


class YesNoDialog(QtWidgets.QDialog):

    def __init__(self, widget, *args, **kwargs):
        super(YesNoDialog, self).__init__(*args, **kwargs)

        btn_accept = QtWidgets.QPushButton("Accept")
        btn_reject = QtWidgets.QPushButton("Cancel")

        btn_accept.setObjectName("AcceptButton")
        btn_reject.setObjectName("CancelButton")
        btn_accept.setDefault(True)
        btn_accept.setEnabled(False)

        layout = QtWidgets.QGridLayout(self)
        layout.addWidget(widget, 0, 0, 1, 2)
        layout.addWidget(btn_accept, 1, 0, 1, 1)
        layout.addWidget(btn_reject, 1, 1, 1, 1)

        btn_accept.clicked.connect(lambda: self.done(self.Accepted))
        btn_reject.clicked.connect(lambda: self.done(self.Rejected))
        if hasattr(widget, "validated"):
            widget.validated.connect(btn_accept.setEnabled)


class ContextNameEditor(QtWidgets.QWidget):
    validated = QtCore.Signal(bool)
    colors = {
        "ready": QtGui.QColor("#78879b"),
        "invalid": QtGui.QColor("#C84747"),
    }

    def __init__(self, existing, default="", *args, **kwargs):
        super(ContextNameEditor, self).__init__(*args, **kwargs)
        self.setMinimumWidth(300)

        validator = RegExpValidator("^[a-zA-Z0-9_.-]*$")

        name = QtWidgets.QLineEdit()
        name.setText(default)
        name.setValidator(validator)
        name.setPlaceholderText("Input context name..")
        name.setToolTip("Only alphanumeric characters A-Z, a-z, 0-9 and "
                        "_, -, . are allowed.")

        message = QtWidgets.QLabel()

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(name)
        layout.addWidget(message)

        timer = QtCore.QTimer(self)

        anim = QtCore.QPropertyAnimation()
        anim.setEasingCurve(QtCore.QEasingCurve.InCubic)
        anim.setDuration(1000)
        anim.setStartValue(self.colors["invalid"])
        anim.setEndValue(self.colors["ready"])

        validator.validated.connect(self.on_validated)
        name.textChanged.connect(self.on_named)
        timer.timeout.connect(lambda: message.setText(""))

        self._timer = timer
        self.animation = anim
        self._status_color = self.colors["ready"]
        self._name = ""
        self._message = message
        self._existing_names = existing

        anim.setTargetObject(self)
        anim.setPropertyName(QtCore.QByteArray(b"status_color"))

        self.validated.emit(False)

    def on_validated(self, state):
        if state == QtGui.QValidator.Invalid:
            self.log("Invalid char.")
            self.animation.stop()
            self.animation.start()

    def on_named(self, value):
        unique_name = value not in self._existing_names
        self._name = value
        self.validated.emit(unique_name and bool(value))
        if not unique_name:
            self.log("Duplicated name.")
            self.animation.stop()
            self.animation.start()

    def get_name(self):
        return self._name

    def log(self, message):
        self._message.setText(str(message))
        self._timer.setSingleShot(True)
        self._timer.start(1000)

    def _get_status_color(self):
        return self._status_color

    def _set_status_color(self, color):
        self._status_color = color
        self.setStyleSheet("border-color: %s;" % color.name())

    status_color = QtCore.Property(QtGui.QColor,
                                   _get_status_color,
                                   _set_status_color)


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
        self.setObjectName("ToolView")
        icon_deg = delegates.IconCenterDelegate(self)
        self.setItemDelegateForColumn(1, icon_deg)  # status icon


class ToolStackWidget(QtWidgets.QWidget):

    def __init__(self, *args, **kwargs):
        super(ToolStackWidget, self).__init__(*args, **kwargs)
        self.setObjectName("ToolStack")

        label = QtWidgets.QLabel("Tool Stack")

        btn_filter = QtWidgets.QPushButton()  # toggleable
        btn_filter.setIcon(res.icon("images", "funnel-fill.svg"))

        view = ToolsView()
        model = ToolStackModel()
        proxy = ToolStackSortProxyModel()

        proxy.setSourceModel(model)
        view.setModel(proxy)
        view.setSortingEnabled(True)
        view.header().setSortIndicatorShown(False)

        # layout

        action_layout = QtWidgets.QVBoxLayout()
        action_layout.addWidget(btn_filter)
        action_layout.addStretch()

        stack_layout = QtWidgets.QHBoxLayout()
        stack_layout.addLayout(action_layout)
        stack_layout.addWidget(view)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(label)
        layout.addLayout(stack_layout)

        # signals

        self._model = model

    def model(self):
        return self._model


class StackedResolveView(QtWidgets.QStackedWidget):
    requested = QtCore.Signal(str, list)
    prefix_changed = QtCore.Signal(str, str)
    suffix_changed = QtCore.Signal(str, str)

    def __init__(self, *args, **kwargs):
        super(StackedResolveView, self).__init__(*args, **kwargs)
        self._add_panel_0()
        self._names = []

    def on_context_added(self, ctx):
        name = ctx.name
        is_first = len(self._names) == 0
        if is_first:
            panel = self.widget(0)
            panel.set_name(name)
            panel.setEnabled(True)
        else:
            self.add_panel(name)
            self.setCurrentIndex(0)

        self._names.insert(0, name)

    def on_context_resolved(self, name, ctx):
        """

        :param name:
        :param ctx:
        :type name: str
        :type ctx: core.SuiteCtx
        :return:
        """
        index = self._names.index(name)
        panel = self.widget(index)
        panel.set_resolved(ctx.context)

    def on_context_renamed(self, name, new_name):
        index = self._names.index(name)
        panel = self.widget(index)
        panel.set_name(new_name)
        self._names.remove(name)
        self._names.insert(index, new_name)

    def on_context_dropped(self, name):
        index = self._names.index(name)
        self._names.remove(name)
        is_empty = len(self._names) == 0

        panel = self.widget(index)
        self.removeWidget(panel)
        if is_empty:
            self._add_panel_0()

    def on_context_selected(self, name):
        # name may not exists yet while the context is just being added.
        if name in self._names:
            self.setCurrentIndex(self._names.index(name))

    def add_panel(self, name, enabled=True):
        panel = ResolvePanel()
        panel.set_name(name)
        panel.setEnabled(enabled)
        panel.prefix_changed.connect(
            lambda text: self.prefix_changed.emit(panel.name(), text)
        )
        panel.suffix_changed.connect(
            lambda text: self.suffix_changed.emit(panel.name(), text)
        )
        panel.requested.connect(
            lambda requests: self.requested.emit(panel.name(), requests)
        )
        self.insertWidget(0, panel)

    def _add_panel_0(self):
        self.add_panel("", enabled=False)


class ResolvePanel(QtWidgets.QWidget):
    requested = QtCore.Signal(list)
    prefix_changed = QtCore.Signal(str)
    suffix_changed = QtCore.Signal(str)

    def __init__(self, *args, **kwargs):
        super(ResolvePanel, self).__init__(*args, **kwargs)

        label = QtWidgets.QLabel()

        naming_editor = QtWidgets.QWidget()
        prefix = QtWidgets.QLineEdit()
        prefix.setPlaceholderText("context prefix..")
        suffix = QtWidgets.QLineEdit()
        suffix.setPlaceholderText("context suffix..")

        request_editor = QtWidgets.QWidget()
        request = RequestTextEdit()
        resolve = QtWidgets.QPushButton("Resolve")
        resolve.setObjectName("ContextResolveOpBtn")

        tools = ResolvedTools()
        packages = ResolvedPackages()
        environ = ResolvedEnvironment()
        code = ResolvedCode()
        graph = ResolvedGraph()

        resolved_info = QtWidgets.QWidget()
        info = QtWidgets.QLabel("Resolved Context Info")
        tabs = QtWidgets.QTabWidget()
        tabs.addTab(tools, "Tools")
        tabs.addTab(packages, "Packages")
        tabs.addTab(environ, "Environment")
        tabs.addTab(code, "Code")
        tabs.addTab(graph, "Graph")

        layout = QtWidgets.QHBoxLayout(naming_editor)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.addWidget(prefix)
        layout.addWidget(suffix)

        layout = QtWidgets.QVBoxLayout(request_editor)
        layout.addWidget(naming_editor)
        layout.addWidget(request)
        layout.addWidget(resolve)

        layout = QtWidgets.QVBoxLayout(resolved_info)
        layout.addWidget(info)
        layout.addWidget(tabs)

        splitter = QtWidgets.QSplitter()
        splitter.addWidget(request_editor)
        splitter.addWidget(resolved_info)

        splitter.setOrientation(QtCore.Qt.Vertical)
        splitter.setChildrenCollapsible(False)
        splitter.setStretchFactor(0, 30)
        splitter.setStretchFactor(1, 70)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(label)
        layout.addWidget(splitter)

        # signal
        prefix.textChanged.connect(
            lambda text: self.prefix_changed.emit(text)
        )
        suffix.textChanged.connect(
            lambda text: self.suffix_changed.emit(text)
        )
        resolve.clicked.connect(
            lambda: self.requested.emit(request.toPlainText().split())
        )

        self._name = None
        self._label = label
        self._tools = tools
        self._packages = packages
        self._environ = environ
        self._code = code
        self._graph = graph

    def name(self):
        return self._name

    def set_name(self, ctx_name):
        """

        :param ctx_name:
        :type ctx_name: str
        :return:
        """
        self._name = ctx_name
        self._tools.set_name(ctx_name)
        self._label.setText("Context: %s" % ctx_name)

    def set_resolved(self, context):
        """

        :param context:
        :type context: rez.ResolvedContext
        :return:
        """
        self._packages.model().load(context.resolved_packages)
        self._environ.model().load(context.get_environ())


class ResolvedTools(QtWidgets.QWidget):

    def __init__(self, *args, **kwargs):
        super(ResolvedTools, self).__init__(*args, **kwargs)

        model = ToolStackModel()
        view = ToolsView()
        view.setModel(model)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(view)

        self._view = view
        self._model = model
        self._view_fixed = False

    def set_name(self, ctx_name):
        if ctx_name and not self._view_fixed:
            index = self._model.find_context_index(ctx_name)
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
            package = index.data(role=ResolvedPackagesModel.PackageRole)
            pkg_uri = os.path.dirname(package.uri)
            fname = os.path.join(pkg_uri, "package.py")
            util.open_file_location(fname)

        def on_copyfile():
            package = index.data(role=ResolvedPackagesModel.PackageRole)
            pkg_uri = os.path.dirname(package.uri)
            fname = os.path.join(pkg_uri, "package.py")
            clipboard = QtWidgets.QApplication.instance().clipboard()
            clipboard.setText(fname)

        openfile.triggered.connect(on_openfile)
        copyfile.triggered.connect(on_copyfile)

        menu.move(QtGui.QCursor.pos())
        menu.show()


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
    pass


class ResolvedGraph(QtWidgets.QWidget):
    pass


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

        refresh = QtWidgets.QPushButton("R")  # todo: need a refresh icon
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

        model.family_updated.connect(self.on_model_family_updated)
        tabs.currentChanged.connect(self.on_tab_clicked)
        search.textChanged.connect(self.on_searched)
        header.sortIndicatorChanged.connect(self.on_sort_changed)
        scroll.valueChanged.connect(self.on_scrolled)
        refresh.clicked.connect(self.on_refresh_clicked)

        self._view = view
        self._model = model
        self._proxy = proxy

        self._tabs = tabs
        self._groups = []

    def model(self):
        return self._model

    def proxy(self):
        return self._proxy

    def on_searched(self, text):
        self._proxy.setFilterRegExp(text)
        self._view.expandAll() if len(text) > 1 else self._view.collapseAll()
        self._view.reset_extension()

    def on_tab_clicked(self, index):
        group = self._tabs.tabText(index)
        item = self._model.first_item_in_initial(group)
        if item is not None:
            index = item.index()
            index = self._proxy.mapFromSource(index)
            self._view.scroll_at_top(index)

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

    def on_refresh_clicked(self):
        self._tabs.setEnabled(False)
        self.refreshed.emit()


class SuiteStorageWidget(QtWidgets.QWidget):

    def __init__(self, *args, **kwargs):
        super(SuiteStorageWidget, self).__init__(*args, **kwargs)

        view = TreeView()
        model = SuiteStorageModel()

        view.setModel(model)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(view)

        self._model = model

    def model(self):
        return self._model
