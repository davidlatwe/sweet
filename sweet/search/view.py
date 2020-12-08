
from ..vendor.Qt5 import QtCore, QtWidgets
from .. import common
from .model import PackageProxyModel

# TODO:
#   * parse request into model item check state
#   * add reset button
#   * log model reset time
#   * no-local-package checkBox
#   * show package paths, and able to update package list per path


class PackageTreeView(common.view.VerticalExtendedTreeView):
    def __init__(self, parent=None):
        super(PackageTreeView, self).__init__(parent=parent)
        self.setObjectName("PackageTreeView")
        self.setSortingEnabled(True)
        self.setAlternatingRowColors(True)
        self.sortByColumn(0, QtCore.Qt.AscendingOrder)

        time_delegate = common.delegate.PrettyTimeDelegate()
        self.setItemDelegateForColumn(1, time_delegate)

        self._delegates = {
            "date": time_delegate
        }


class PackageTabBar(common.view.VerticalDocTabBar):
    def __init__(self, parent=None):
        super(PackageTabBar, self).__init__(parent=parent)
        self.setObjectName("PackageTabBar")
        self.setMinimumHeight(120)


class PackageView(QtWidgets.QWidget):
    """Single page tab widget"""
    def __init__(self, parent=None):
        super(PackageView, self).__init__(parent=parent)
        self.setObjectName("PackageView")

        widgets = {
            "search": QtWidgets.QLineEdit(),
            "book": QtWidgets.QWidget(),
            "page": QtWidgets.QWidget(),
            "side": QtWidgets.QWidget(),
            "view": PackageTreeView(),
            "tab": PackageTabBar(),
        }
        widgets["page"].setObjectName("PackagePage")
        widgets["side"].setObjectName("PackageSide")

        widgets["search"].setPlaceholderText(" Search by family or tool..")

        # Layouts..
        layout = QtWidgets.QVBoxLayout(widgets["side"])
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(widgets["tab"])
        layout.addStretch(100)
        layout.setSpacing(0)

        layout = QtWidgets.QVBoxLayout(widgets["page"])
        layout.setContentsMargins(2, 2, 2, 2)
        layout.addWidget(widgets["view"])

        layout = QtWidgets.QHBoxLayout(widgets["book"])
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(widgets["side"])
        layout.addWidget(widgets["page"])
        layout.setSpacing(0)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(widgets["search"])
        layout.addSpacing(6)
        layout.addWidget(widgets["book"])
        layout.setSpacing(0)

        # Signals..
        header = widgets["view"].header()
        scroll = widgets["view"].verticalScrollBar()

        widgets["tab"].currentChanged.connect(self.on_tab_clicked)
        widgets["search"].textChanged.connect(self.on_searched)
        header.sortIndicatorChanged.connect(self.on_sort_changed)
        scroll.valueChanged.connect(self.on_scrolled)

        self._widgets = widgets
        self._groups = []

    def init_column_width(self):
        # ignore this if window geo saved
        self._widgets["view"].setColumnWidth(0, 180)  # name
        self._widgets["view"].setColumnWidth(1, 120)  # date

    def set_model(self, model):
        proxy = PackageProxyModel()
        proxy.setSourceModel(model)
        self._widgets["view"].setModel(proxy)

        model.modelReset.connect(self.on_model_reset)

    def model(self):
        proxy = self._widgets["view"].model()
        return proxy.sourceModel()

    def proxy(self):
        return self._widgets["view"].model()

    def on_searched(self, text):
        view = self._widgets["view"]
        proxy = self.proxy()
        proxy.setFilterRegExp(text)
        view.reset_extension()

    def on_tab_clicked(self, index):
        tab = self._widgets["tab"]
        view = self._widgets["view"]
        proxy = self.proxy()
        model = self.model()

        group = tab.tabText(index)
        for i, item in enumerate(model.iter_items()):
            if item["_group"] == group:
                index = model.index(i, 0)
                index = proxy.mapFromSource(index)
                view.scroll_at_top(index)
                return

    def on_scrolled(self, value):
        if not self._widgets["tab"].isEnabled():
            return

        tab = self._widgets["tab"]
        view = self._widgets["view"]
        proxy = self.proxy()
        model = self.model()

        index = view.top_scrolled_index(value)
        index = proxy.mapToSource(index)
        name = model.data(index)
        if name:
            group = name[0].upper()
            index = self._groups.index(group)
            tab.blockSignals(True)
            tab.setCurrentIndex(index)
            tab.blockSignals(False)

    def on_sort_changed(self, index, order):
        is_sort_name = index == 0
        tab = self._widgets["tab"]

        tab.setEnabled(is_sort_name)
        if is_sort_name:
            if len(self._groups) <= 1:
                return

            first, second = self._groups[:2]
            is_ascending = int(first > second)
            if is_ascending == int(order):
                return

            self._groups.reverse()
            for i, group in enumerate(self._groups):
                tab.setTabText(i, group)

    def on_model_reset(self):
        tab = self._widgets["tab"]
        model = self.model()

        self._groups.clear()
        for index in range(tab.count()):
            tab.removeTab(index)

        for group in model.name_groups():
            self._groups.append(group)
            tab.addTab(group)

        # (MacOS) Ensure tab bar *polished* even it's not visible on launch.
        tab.updateGeometry()
