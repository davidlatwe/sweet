
from Qt5 import QtWidgets
from .. import common
from .model import PackageProxyModel


class PackageView(QtWidgets.QWidget):
    """Single page tab widget"""

    def __init__(self, parent=None):
        super(PackageView, self).__init__(parent=parent)

        widgets = {
            "search": QtWidgets.QLineEdit(),
            "book": QtWidgets.QWidget(),
            "page": QtWidgets.QWidget(),
            "side": QtWidgets.QWidget(),
            "view": common.view.VerticalExtendedTreeView(),
            "tab": common.view.VerticalDocTabBar(),
        }

        # TODO:
        # * parse request into model item check state
        # * add reset button
        # * log model reset time

        self.setObjectName("PackageBook")
        widgets["view"].setObjectName("PackageTreeView")
        widgets["tab"].setObjectName("PackageTab")
        widgets["page"].setObjectName("BookPage")
        widgets["side"].setObjectName("BookSide")

        layout = QtWidgets.QVBoxLayout(widgets["side"])
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(widgets["tab"])
        layout.addStretch(100)
        layout.setSpacing(0)

        layout = QtWidgets.QVBoxLayout(widgets["page"])
        layout.setContentsMargins(6, 6, 6, 6)
        layout.addWidget(widgets["view"])
        layout.setSpacing(0)

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

        widgets["tab"].setMinimumHeight(120)
        widgets["search"].setPlaceholderText(" Search by family or tool..")

        widgets["tab"].currentChanged.connect(self.on_tab_clicked)
        widgets["search"].textChanged.connect(self.on_searched)
        scroll = widgets["view"].verticalScrollBar()
        scroll.valueChanged.connect(self.on_scrolled)

        self._widgets = widgets
        self._groups = []

    def setModel(self, model):
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

    def on_model_reset(self):
        tab = self._widgets["tab"]
        model = self.model()

        self._groups.clear()
        for index in range(tab.count()):
            tab.removeTab(index)

        for group in model.name_groups():
            self._groups.append(group)
            tab.addTab(group)

    def reset(self, data):
        model = self.model()
        model.reset(data)
