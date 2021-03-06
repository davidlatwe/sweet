
import os
from ..vendor.Qt5 import QtCore, QtGui, QtWidgets
from .. import util
from .model import ResolvedPackageModel
from ..common.delegate import TableViewRowHover
from ..common.model import CompleterProxyModel
from ..common.view import (
    JsonView,
    SlimTableView,
    RequestTextEdit,
    RequestCompleter,
)


class SuiteContextTab(QtWidgets.QTabWidget):

    def __init__(self, parent=None):
        super(SuiteContextTab, self).__init__(parent=parent)
        self._tab_by_id = dict()

    def addTab(self, tab, *args, **kwargs):
        self._tab_by_id[tab.id()] = tab
        return super(SuiteContextTab, self).addTab(tab, *args, **kwargs)

    def set_title(self, widget, text):
        index = self.indexOf(widget)
        self.setTabText(index, text)

    def show_context(self, widget):
        self.setCurrentWidget(widget)

    def remove_context(self, id_):
        widget = self._tab_by_id.pop(id_)
        index = self.indexOf(widget)
        self.removeTab(index)
        widget.deleteLater()


class ContextResolveView(QtWidgets.QWidget):
    requested = QtCore.Signal(str, list)

    def __init__(self, context_id, parent=None):
        super(ContextResolveView, self).__init__(parent=parent)
        self._id = context_id

        panels = {
            "options": QtWidgets.QWidget(),
            "request": QtWidgets.QWidget(),
            "split": QtWidgets.QSplitter(),
            "resolved": ResolvedContextView(),
        }
        panels["options"].setObjectName("ContextOperationBar")

        dialogs = {
            "timestamp": TimestampDialog(self),
        }

        widgets = {
            "filter": QtWidgets.QPushButton(),  # TODO: package filter
            "timestamp": QtWidgets.QPushButton(),  # TODO: not complete yet
            "building": QtWidgets.QPushButton(),  # TODO: set resolve build env
            "parse": QtWidgets.QPushButton(),  # TODO: set request from search
            "request": RequestTextEdit(),
            "resolve": QtWidgets.QPushButton("Resolve"),
        }
        widgets["resolve"].setObjectName("ContextResolveOpBtn")
        widgets["parse"].setObjectName("ContextParseRequestOpBtn")
        widgets["timestamp"].setObjectName("ContextTimestampOpBtn")
        widgets["filter"].setObjectName("ContextFilterOpBtn")
        widgets["building"].setObjectName("ContextBuildingOpBtn")

        widgets["request"].setPlaceholderText("requests..")
        widgets["request"].setAcceptRichText(False)
        widgets["request"].setTabChangesFocus(True)

        # layout..
        layout = QtWidgets.QHBoxLayout(panels["options"])
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(widgets["parse"])
        layout.addWidget(widgets["filter"])
        layout.addWidget(widgets["timestamp"])
        layout.addWidget(widgets["building"])
        layout.setAlignment(QtCore.Qt.AlignLeft)

        layout = QtWidgets.QVBoxLayout(panels["request"])
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(panels["options"])
        layout.addWidget(widgets["request"])
        layout.addWidget(widgets["resolve"])

        panels["split"].setOrientation(QtCore.Qt.Vertical)
        panels["split"].addWidget(panels["request"])
        panels["split"].addWidget(panels["resolved"])

        layout = QtWidgets.QHBoxLayout(self)
        layout.addWidget(panels["split"])

        panels["split"].setStretchFactor(0, 20)
        panels["split"].setStretchFactor(1, 80)

        # signals..
        widgets["resolve"].clicked.connect(self.on_resolve_clicked)
        widgets["timestamp"].clicked.connect(self.on_timestamp_clicked)

        self._panels = panels
        self._dialogs = dialogs
        self._widgets = widgets

    def id(self):
        return self._id

    def setup_request_completer(self, model):
        requester = self._widgets["request"]
        completer = RequestCompleter(requester)
        completer.setModelSorting(completer.CaseInsensitivelySortedModel)
        completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
        completer.setWrapAround(False)

        proxy = CompleterProxyModel()
        proxy.setSourceModel(model)
        completer.setCompletionColumn(model.CompletionColumn)
        completer.setCompletionRole(model.CompletionRole)
        completer.setModel(proxy)

        requester.setCompleter(completer)
        self._widgets["completer"] = completer

    def set_models(self, packages, environment):
        self._panels["resolved"].set_models(packages, environment)

    def on_resolve_clicked(self):
        request = self._widgets["request"].toPlainText()
        self.requested.emit(self._id, request.split())

    def on_timestamp_clicked(self):
        dialog = self._dialogs["timestamp"]
        if dialog.exec_():
            print(dialog.timestamp())

    def set_requests(self, text):
        self._widgets["request"].setText(text)


class ResolvedContextView(QtWidgets.QTabWidget):

    def __init__(self, parent=None):
        super(ResolvedContextView, self).__init__(parent=parent)

        pages = {
            "packages": ResolvedPackagesView(),
            "environment": JsonView(),
            # code,
            # graph,
        }

        pages["packages"].setItemDelegate(TableViewRowHover())
        pages["packages"].setAlternatingRowColors(True)

        self.addTab(pages["packages"], "Packages")
        self.addTab(pages["environment"], "Environment")

        self._pages = pages

    def set_models(self, packages, environment):
        self._pages["packages"].setModel(packages)
        self._pages["environment"].setModel(environment)


class ResolvedPackagesView(SlimTableView):

    def __init__(self, parent=None):
        super(ResolvedPackagesView, self).__init__(parent=parent)
        self.setObjectName("ResolvedPackagesView")
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.on_right_click)

    def on_right_click(self, position):
        index = self.indexAt(position)

        if not index.isValid():
            # Clicked outside any item
            return

        menu = QtWidgets.QMenu(self)
        openfile = QtWidgets.QAction("Open file location", menu)
        copyfile = QtWidgets.QAction("Copy file location", menu)

        menu.addAction(openfile)
        menu.addAction(copyfile)

        def on_openfile():
            package = index.data(role=ResolvedPackageModel.PackageRole)
            pkg_uri = os.path.dirname(package.uri)
            fname = os.path.join(pkg_uri, "package.py")
            util.open_file_location(fname)

        def on_copyfile():
            package = index.data(role=ResolvedPackageModel.PackageRole)
            pkg_uri = os.path.dirname(package.uri)
            fname = os.path.join(pkg_uri, "package.py")
            clipboard = QtWidgets.QApplication.instance().clipboard()
            clipboard.setText(fname)

        openfile.triggered.connect(on_openfile)
        copyfile.triggered.connect(on_copyfile)

        menu.move(QtGui.QCursor.pos())
        menu.show()


class TimestampDialog(QtWidgets.QDialog):

    def __init__(self, parent=None):
        super(TimestampDialog, self).__init__(parent=parent)

        widgets = {
            "calendar": QtWidgets.QCalendarWidget(),
            "clock": None,
            "accept": QtWidgets.QPushButton("Accept"),
            "reject": QtWidgets.QPushButton("Cancel"),
        }
        widgets["accept"].setObjectName("AcceptButton")
        widgets["reject"].setObjectName("CancelButton")

        widgets["accept"].setDefault(True)

        layout = QtWidgets.QGridLayout(self)
        layout.addWidget(widgets["calendar"], 0, 0, 1, -1)
        layout.addWidget(widgets["accept"], 1, 0, 1, 1)
        layout.addWidget(widgets["reject"], 1, 1, 1, 1)

        widgets["accept"].clicked.connect(self.on_accepted)
        widgets["reject"].clicked.connect(self.on_rejected)

        self._widgets = widgets

    def on_accepted(self):
        self.done(self.Accepted)

    def on_rejected(self):
        self.done(self.Rejected)

    def timestamp(self):
        return self._widgets["calendar"].selectedDate()
