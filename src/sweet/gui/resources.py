
import re
import math
from dataclasses import dataclass
from collections import OrderedDict as odict
from ._vendor.Qt5 import QtCore, QtGui, QtWidgets

_themes = odict()


def load_themes():
    _themes.clear()
    for theme in default_themes():
        _themes[theme.name] = theme


def theme_names():
    for name in _themes.keys():
        yield name


def load_theme(name=None):
    if name:
        theme = _themes.get(name)
        if theme is None:
            print("No theme named: %s" % name)
            return
    else:
        theme = next(iter(_themes.values()))

    return theme.style_sheet()


def default_themes():
    Resources.load()
    return [
        BaseLightTheme(),
        BaseDarkTheme(),
    ]


class Resources:
    fonts = (
        "opensans/OpenSans-Bold.ttf",
        "opensans/OpenSans-Italic.ttf",
        "opensans/OpenSans-Regular.ttf",
        "jetbrainsmono/JetBrainsMono-Regular.ttf"
    )
    icons_ext = ".png", ".svg"

    @classmethod
    def load(cls):
        from . import sweet_rc  # noqa
        font_db = QtGui.QFontDatabase
        for f in cls.fonts:
            font_db.addApplicationFont(":/fonts/" + f)
        cls._font_loaded = True

    _font_loaded = False
    _x_width = None
    _x_scale = None
    _x_scale_baseline = 13
    """This baseline is coming from the width of char 'x' in font 'Open Sans'
    with my 4K screen on Windows.
    """

    @classmethod
    def x_width(cls):
        # note: there's QFontMetrics.fontDpi() after Qt5.14 which may also works
        if not cls._font_loaded:
            cls.load()
        if cls._x_width is None:
            m = QtGui.QFontMetrics(QtGui.QFont("Open Sans", 12))
            size = m.size(QtCore.Qt.TextSingleLine, "x")
            cls._x_width = size.width()
        return cls._x_width

    @classmethod
    def x_scale(cls):
        if cls._x_scale is None:
            cls._x_scale = cls.x_width() / cls._x_scale_baseline
            cls._x_scale *= cls.hdpi_scale()
        return cls._x_scale

    _density = None
    _hdpi_scale = None

    @classmethod
    def pixel_density(cls):
        if cls._density is None:
            _a = QtWidgets.QApplication.instance() or QtWidgets.QApplication()
            _screen = _a.screenAt(QtGui.QCursor.pos())
            cls._density = _screen.devicePixelRatio()
        return cls._density

    @classmethod
    def hdpi_scale(cls):
        if cls._hdpi_scale is None:
            _a = QtWidgets.QApplication.instance() or QtWidgets.QApplication()
            _screen = _a.screenAt(QtGui.QCursor.pos())
            cls._hdpi_scale = (_screen.physicalDotsPerInch() / 96.0) \
                if cls.pixel_density() > 1 else 1
        return cls._hdpi_scale


def px(value):
    """Return a scaled value, for HDPI resolutions

    https://doc.qt.io/qt-5/highdpi.html
    Although Qt provides some env vars and q-attributes for supporting
    cross-platform high-DPI scaling, I find scaling px with these factors
    has the best result.

    """
    return PX(value * Resources.x_scale())


@dataclass
class PX:
    v: float

    def __str__(self):
        return f"{self.v}px"

    def __int__(self):
        return int(self.v)

    def __float__(self):
        return float(self.v)

    @property
    def floor(self):
        return PX(math.floor(self.v))

    @property
    def ceil(self):
        return PX(math.ceil(self.v))


@dataclass
class HSL:
    """
    The value of s, v, l and a in hsv(), hsva() hsl() or hsla() must
    all be in the range 0-255 or with percentages, the value of h must
    be in the range 0-359.
    """
    h: float
    s: float
    l: float

    def __str__(self):
        return f"hsl({self.h}, {self.s}%, {self.l}%)"

    def __mul__(self, other: float):
        self.l *= other
        return self

    def __add__(self, other: float):
        self.l += other
        return self


@dataclass
class Palette:
    # primary color platte
    primary: HSL
    primary_bright: HSL
    primary_dimmed: HSL
    # secondary color platte
    secondary: HSL
    secondary_bright: HSL
    secondary_dimmed: HSL
    # base colors
    surface: HSL
    background: HSL
    # additional colors
    error: HSL
    warning: HSL
    # texts
    on_primary: HSL
    on_secondary: HSL
    on_surface: HSL
    on_background: HSL
    on_error: HSL
    on_warning: HSL


class BaseLightTheme(object):
    name = "sweet-light"
    palette = Palette(
        primary=HSL(35.67, 100.00, 57.45),          # Orange 400
        primary_bright=HSL(53.88, 100.00, 61.57),   # Yellow 500
        primary_dimmed=HSL(35.91, 100.00, 75.10),   # Orange 200

        secondary=HSL(15.88, 15.32, 56.47),         # Brown 300
        secondary_bright=HSL(15.71, 17.50, 47.06),  # Brown 400
        secondary_dimmed=HSL(16.00, 15.79, 81.37),  # Brown 100

        surface=HSL(0.00, 0.00, 74.12),             # Grey 400
        background=HSL(0.00, 0.00, 98.04),          # Grey 50

        error=HSL(11.95, 100.00, 43.33),            # Deep Orange A700
        warning=HSL(40.24, 100.00, 50.00),          # Amber A700

        on_primary=HSL(0.00, 0.00, 25.88),          # Grey 800
        on_secondary=HSL(0.00, 0.00, 25.89),        # Grey 800.01
        on_surface=HSL(200.00, 15.63, 62.35),       # Blue Grey 300
        on_background=HSL(200.00, 15.63, 62.36),    # Blue Grey 300.01
        on_error=HSL(0.00, 0.00, 12.94),            # Grey 900
        on_warning=HSL(0.00, 0.00, 12.95),          # Grey 900.01
    )

    def __init__(self):
        self._composed = ""

    def style_sheet(self, refresh=False):
        if not self._composed or refresh:
            self.compose_styles()
        return self._composed

    def compose_styles(self):
        self._composed = ""
        for name in self.__dir__():
            if name.startswith("_q_"):
                self._composed += getattr(self, name)()

    def _q_global(self):
        return f"""
        * {{
            border: none;
            outline: none;
            font-family: "Open Sans";
            color: {self.palette.on_primary};  /* text color */
            border-color: {self.palette.background};
            background-color: {self.palette.background};
        }}
        """

    def _q_widget(self):
        return f"""

        QWidget:focus {{
            border: 1px solid {self.palette.on_surface * 1.5};
        }}
        QWidget:disabled {{
            color: {self.palette.on_background};
        }}

        """

    def _q_label(self):
        return f"""
        
        QLabel {{
            padding-top: {px(2).floor};
            padding-bottom: {px(2).floor};
        }}

        """

    def _q_button(self):
        return f"""

        QPushButton {{
            background-color: {self.palette.background};
            border: 1px solid {self.palette.on_background};
            border-radius: 0px;
            min-height: {px(24).ceil};
            padding: {px(8).ceil};
        }}
        QPushButton:hover {{
            background-color: {self.palette.background};
            border: 1px solid {self.palette.primary};
        }}
        QPushButton:pressed {{
            background-color: {self.palette.surface};
            border: 1px dashed {self.palette.on_background};
        }}
        QPushButton:focus:!hover {{
            background-color: {self.palette.background};
            border: 1px solid {self.palette.on_background};
            font-weight: bold;
        }}

        """

    def _q_check_box(self):
        return f"""

        QCheckBox {{
            spacing: {px(5).floor};
            margin-bottom: {px(2).floor};
        }}
        QCheckBox:focus {{
            border: none;
        }}
        QCheckBox::indicator {{
            width: {px(15).floor};
            height: {px(15).floor};
            background-color: {self.palette.background};
        }}
        QCheckBox::indicator:unchecked {{
            image: url(:/icons/checkbox_unchecked.png);
        }}
        QCheckBox::indicator:unchecked:disabled {{
            image: url(:/icons/checkbox_unchecked_dim.png);
        }}
        QCheckBox::indicator:checked {{
            image: url(:/icons/checkbox_checked.png);
        }}
        QCheckBox::indicator:checked:disabled {{
            image: url(:/icons/checkbox_checked_dim.png);
        }}
        QCheckBox::indicator:indeterminate {{
            image: url(:/icons/checkbox_indeterminate.png);
        }}
        QCheckBox::indicator:indeterminate:disabled {{
            image: url(:/icons/checkbox_indeterminate_dim.png);
        }}

        """

    def _q_menu(self):
        return f"""

        QMenu {{
            padding-top: {px(2)};
            padding-bottom: {px(2)};
            background-color: {self.palette.surface};
            border: 1px solid transparent;
        }}
        QMenu::item {{
            padding: {px(5)} {px(16)} {px(5)} {px(16)};
            margin-left: {px(5)};
        }}
        QMenu::item:!selected {{
            color: {self.palette.on_surface};
        }}
        QMenu::item:selected {{
            color: {self.palette.on_secondary};
            background-color: {self.palette.secondary};
        }}
        QMenu::item:disabled {{
            color: {self.palette.surface};
        }}
        QMenu::indicator {{
            width: {px(12)};
            height: {px(12)};
            margin-left: {px(4)};
        }}
        QMenu::indicator::non-exclusive:checked {{
            image: url(:/icons/checkbox_checked.png);
        }}
        QMenu::indicator::non-exclusive:unchecked {{
            image: url(:/icons/checkbox_unchecked.png);
        }}
        QMenu::indicator:exclusive:checked {{
            image: url(:/icons/checkbox_checked.png);
        }}
        QMenu::indicator:exclusive:unchecked {{
            image: url(:/icons/checkbox_unchecked.png);
        }}

        """

    def _q_frame(self):
        # separator line
        return f"""

        .QFrame {{
            color: {self.palette.on_background};
        }}

        """

    def _q_tabs(self):
        # note: "border: none" does not equal to "border: 1px solid transparent",
        #          there still 1px difference and may affect text position in tab
        return f"""
        
        QTabBar {{qproperty-drawBase: 0;}}

        QTabWidget {{
            border: none;
        }}
        QTabWidget::pane {{
            border: 1px solid {self.palette.on_surface};
            border-radius: 0px;
            padding: {px(3)};
        }}

        QTabBar:focus {{
            border: 0px transparent;
        }}

        QTabBar::tab {{
            background-color: {self.palette.surface};
            border: 1px solid {self.palette.on_surface};
            padding: {px(5)};
        }}
        QTabBar::tab:!selected {{
            color: {self.palette.on_background};
            background-color: {self.palette.background};
        }}
        QTabBar::tab:!selected:hover {{
            color: {self.palette.on_primary};
            background-color: {self.palette.primary};
        }}
        
        /* top */

        QTabBar::tab::top {{
            border-right: none;
            border-bottom: none;
        }}
        QTabBar::tab::top:only-one {{
            border-right: 1px solid {self.palette.on_surface};
        }}
        QTabBar::tab::top:last {{
            border-right: 1px solid {self.palette.on_surface};
        }}
        
        /* bottom */

        QTabBar::tab::bottom {{
            border-right: none;
            border-top: none;
        }}
        QTabBar::tab::bottom:only-one {{
            border-right: 1px solid {self.palette.on_surface};
        }}
        QTabBar::tab::bottom:last {{
            border-right: 1px solid {self.palette.on_surface};
        }}
        
        /* left */

        QTabBar::tab::left {{
            color: {self.palette.on_background};
            background-color: {self.palette.on_background};
            border: 1px solid {self.palette.on_surface};
            border-bottom: 1px solid transparent;
            padding: {px(8)};
        }}
        QTabBar::tab::left:next-selected {{
            border-top: 1px solid {self.palette.on_surface};
        }}
        QTabBar::tab::left:selected {{
            color: {self.palette.on_surface};
            background-color: {self.palette.surface};
            border: 1px solid {self.palette.on_surface};
            border-right: 1px solid transparent;
        }}
        QTabBar::tab::left:previous-selected {{
            border-top: 1px solid transparent;
        }}
        QTabBar::tab::left:!selected {{
            color: {self.palette.on_background};
            background-color: {self.palette.background};
            border-right: 1px solid {self.palette.on_surface};
            margin-left: {px(3)};
            padding-left: {px(5)};
        }}
        QTabBar::tab::left:last:!selected {{
            border-bottom: 1px solid {self.palette.on_surface};
        }}
        QTabBar::tab::left:last:selected {{
            border-bottom: 1px solid {self.palette.on_surface};
        }}
        QTabBar::tab::left:!selected:hover {{
            color: {self.palette.on_primary};
            background-color: {self.palette.primary};
        }}
        QTabBar::tab::left:disabled {{
            color: {self.palette.on_background};
            background-color: {self.palette.background};
            border: 1px solid {self.palette.background};
            border-right: 1px solid {self.palette.on_surface};
            border-bottom: 1px solid transparent;
            margin-left: {px(3)};
            padding-left: {px(5)};
        }}
        QTabBar::tab::left:disabled:selected {{
            color: {self.palette.on_background};
            background-color: {self.palette.background};
            border: 1px solid {self.palette.background};
            border-right: 1px solid {self.palette.on_surface};
            border-bottom: 1px solid transparent;
            margin-left: {px(3)};
            padding-left: {px(5)};
        }}
        QTabBar::tab::left:disabled:previous-selected {{
            border-top: 1px solid {self.palette.on_surface};
        }}
        QTabBar::tab::left:disabled:last {{
            border-bottom: 1px solid {self.palette.background};
        }}
        
        /* right (not defined) */

        /* others */

        QTabBar::scroller {{
            width: {px(24).floor};
        }}
        QTabBar QToolButton {{
            color: {self.palette.on_surface};
            background-color: {self.palette.surface};
            border: 1px solid {self.palette.on_surface};
        }}
        QTabBar QToolButton:disabled {{
            color: {self.palette.on_background};
            background-color: {self.palette.background};
            border: 1px solid {self.palette.on_background};
        }}
        
        """

    def _q_splitter(self):
        return f"""

        QSplitter::handle:vertical {{
            height: 0px;
            margin: {px(4)};
            padding: -{px(3)};
            background-color: transparent;
            border: 1px dotted {self.palette.on_primary};
        }}
        QSplitter::handle:vertical:hover {{
            background-color: transparent;
            border: 1px dotted {self.palette.on_surface};
        }}
        QSplitter::handle:horizontal {{
            width: 0px;
            margin: {px(4)};
            padding: -{px(3)};
            background-color: transparent;
            border: 1px dotted {self.palette.on_primary};
        }}
        QSplitter::handle:horizontal:hover {{
            background-color: transparent;
            border: 1px dotted {self.palette.on_surface};
        }}
        
        QSplitterHandle:hover {{}} /*https://bugreports.qt.io/browse/QTBUG-13768*/

        """

    def _q_header(self):
        return f"""

        QHeaderView {{
            border: none;
            font-weight: normal;
        }}
        QHeaderView::section {{
            padding: 0px;
            padding-left: {px(5).floor};
            padding-right: {px(5).ceil};
            padding-top: {px(5).ceil};
            background: {self.palette.background};
            border-top: none;
            border-bottom: 1px solid {self.palette.on_secondary};
            border-left: none;
            border-right: none;
        }}
        QHeaderView::section:first {{
            border-left: none;
        }}
        QHeaderView::section:last {{
            border-right: none;
        }}
        QHeaderView:down-arrow {{
            image: url(:/icons/chevron_down.svg);
            subcontrol-position: top center;
            height: {px(8).floor};
            width: {px(8).floor};
        }}
        QHeaderView:up-arrow {{
            image: url(:/icons/chevron_up.svg);
            subcontrol-position: top center;
            height: {px(8).floor};
            width: {px(8).floor};
        }}

        """

    def _q_tree_view(self):
        return f"""

        QAbstractItemView {{
            show-decoration-selected: 1;  /* highlight decoration (branch) */
            background-color: {self.palette.background};
            alternate-background-color: {self.palette.background};
            border: none;
            selection-color: {self.palette.on_primary};
            selection-background-color: {self.palette.primary};
        }}
        QAbstractItemView:focus {{
            border: none;
        }}
        QAbstractItemView::item:selected:active {{
            background-color: {self.palette.secondary};
        }}
        QAbstractItemView::item:selected:!focus {{
            background-color: {self.palette.secondary};
        }}
        QAbstractItemView::item:hover {{
            color: {self.palette.on_primary};
            background-color: {self.palette.primary};
        }}
        QAbstractItemView::item:hover:selected {{
            color: {self.palette.on_primary};
            background-color: {self.palette.primary};
        }}
        QTreeView::branch::has-children::!has-siblings:closed {{
            image: url(:/icons/caret-right-fill.svg);
        }}
        QTreeView::branch:closed::has-children::has-siblings {{
            image: url(:/icons/caret-right-fill.svg);
        }}
        QTreeView::branch:open::has-children::!has-siblings {{
            image: url(:/icons/caret-down-fill.svg);
        }}
        QTreeView::branch:open::has-children::has-siblings {{
            image: url(:/icons/caret-down-fill.svg);
        }}
        QTreeView::branch::has-children::!has-siblings:closed:hover {{
            image: url(:/icons/caret-right-fill-on.svg);
        }}
        QTreeView::branch:closed::has-children::has-siblings:hover {{
            image: url(:/icons/caret-right-fill-on.svg);
        }}
        QTreeView::branch:open::has-children::!has-siblings:hover {{
            image: url(:/icons/caret-down-fill-on.svg);
        }}
        QTreeView::branch:open::has-children::has-siblings:hover {{
            image: url(:/icons/caret-down-fill-on.svg);
        }}
        QTreeView::branch:selected {{
            background-color: {self.palette.secondary};
        }}
        QTreeView::branch:hover {{
            background-color: {self.palette.primary};
        }}
        
        """

    def _q_dialog(self):
        return f"""

        #AcceptButton {{
            icon: url(:/icons/check-ok.svg);
        }}
        #CancelButton {{
            icon: url(:/icons/x.svg);
        }}
        
        """

    def _q_installed_packages(self):
        return f"""

        #PackageView {{
            background-color: {self.palette.background};
        }}
        #PackagePage {{
            background-color: {self.palette.background};
            border: 1px solid {self.palette.on_surface};
            border-left: none;
        }}
        #PackageSide {{
            background-color: transparent;
            border: none;
            border-right: 1px solid {self.palette.on_surface};
        }}

        """

    def _q_context_buttons(self):
        # qstylilzer bug:
        #   AttributeError: 'PseudoStateRule' object has no attribute 'icon'
        #
        # also:
        #   property `icon` is available since 5.15. (only for QPushButton)
        #   https://doc.qt.io/qt-5/stylesheet-reference.html#icon
        #
        return f"""

        #ContextResolveOpBtn {{
            icon: url(:/icons/lightning-fill-dim.svg);
        }}
        #ContextResolveOpBtn:hover {{
            icon: url(:/icons/lightning-fill.svg);
        }}
        #ContextAddOpBtn {{
            icon: url(:/icons/plus.svg);
        }}
        #ContextAddOpBtn:hover {{
            icon: url(:/icons/plus.svg);
        }}
        #ContextRemoveOpBtn {{
            icon: url(:/icons/trash-fill-dim.svg);
        }}
        #ContextRemoveOpBtn:hover {{
            icon: url(:/icons/trash-fill.svg);
        }}

        """

    def _q_suite_bar(self):
        return f"""

        #SuiteNameEdit {{
            font-size: {px(30).ceil};
        }}
        #SuiteSaveButton {{
            min-height: {px(24).floor};
            min-width: {px(160).ceil};
            icon: url(:/icons/egg-fried-dim.svg);
        }}
        #SuiteSaveButton:hover {{
            icon: url(:/icons/egg-fried.svg);
        }}
        #SuiteNewButton {{
            min-height: {px(24).floor};
            min-width: {px(160).ceil};
            icon: url(:/icons/egg-fill-dim.svg);
        }}
        #SuiteNewButton:hover {{
            icon: url(:/icons/egg-fill.svg);
        }}

        """

    def _q_requests(self):
        return f"""

        #RequestTextEdit,
        #RequestTableEdit {{
            font-family: "JetBrains Mono";
        }}

        """

    def _q_tool_view(self):
        return f"""

        #ToolsView::item {{
            padding-left: {px(4).floor};
        }}
        #ToolsView::indicator:unchecked {{
            image: url(:icons/toggle-off.svg);
        }}
        #ToolsView::indicator:unchecked:hover {{
            image: url(:icons/toggle-off-bright.svg);
        }}
        #ToolsView::indicator:unchecked:disabled {{
            image: url(:icons/toggle-off-dim.svg);
        }}
        #ToolsView::indicator:checked {{
            image: url(:icons/toggle-on.svg);
        }}
        #ToolsView::indicator:checked:hover {{
            image: url(:icons/toggle-on-bright.svg);
        }}
        #ToolsView::indicator:checked:disabled {{
            image: url(:icons/toggle-on-dim.svg);
        }}

        """


class BaseDarkTheme(BaseLightTheme):
    name = "sweet-dark"
    palette = Palette(
        primary=HSL(35.67, 100.00, 57.45),  # Orange 400
        primary_bright=HSL(53.88, 100.00, 61.57),  # Yellow 500
        primary_dimmed=HSL(35.91, 100.00, 75.10),  # Orange 200

        secondary=HSL(15.88, 15.32, 56.47),  # Brown 300
        secondary_bright=HSL(15.71, 17.50, 47.06),  # Brown 400
        secondary_dimmed=HSL(16.00, 15.79, 81.37),  # Brown 100

        surface=HSL(0.00, 0.00, 74.12),  # Grey 400
        background=HSL(0.00, 0.00, 87.84),  # Grey 300

        error=HSL(11.95, 100.00, 43.33),  # Deep Orange A700
        warning=HSL(40.24, 100.00, 50.00),  # Amber A700

        on_primary=HSL(0.00, 0.00, 25.88),  # Grey 800
        on_secondary=HSL(0.00, 0.00, 25.88),  # Grey 800
        on_surface=HSL(200.00, 15.63, 62.35),  # Blue Grey 300
        on_background=HSL(200.00, 15.63, 62.35),  # Blue Grey 300
        on_error=HSL(0.00, 0.00, 12.94),  # Grey 900
        on_warning=HSL(0.00, 0.00, 12.94),  # Grey 900
    )


# todo:
"""
#Preference QScrollArea {
    border: 1px solid %(border.bright)s;
}

#ContextOperationBar QPushButton {
    max-width: 18px;
    max-height: 18px;
    min-width: 18px;
    min-height: 18px;
    padding: 2px;
    border: none;
    background-color: transparent;
}

#ContextView QLineEdit {
    background-color: %(background.bright)s;
}

#DocStrings {
    color: %(on.dim.surface)s;
}

"""


"""
QAbstractScrollArea {
    background-color: %(background.bright)s;
}

QScrollBar:horizontal {
    background-color: %(background.bright)s;
    height: 10px;
    border: none;
    margin: 0px 10px 0px 10px;
}

QScrollBar::handle:horizontal {
    background-color: %(primary.bright)s;
    min-width: 20px;
    margin: 1px 1px 0px 1px;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    background-color: %(background.bright)s;
    border-top: 1px solid %(background.bright)s;
    margin: 1px 0px 0px 0px;
    height: 10px;
    width: 10px;
}

QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: none;
}

QScrollBar::sub-line:horizontal {
    image: url(%(res)s/chevron_left.svg);
    subcontrol-position: left;
    subcontrol-origin: margin;
}

QScrollBar::add-line:horizontal {
    image: url(%(res)s/chevron_right.svg);
    subcontrol-position: right;
    subcontrol-origin: margin;
}


QScrollBar:vertical {
    background-color: %(background.bright)s;
    width: 10px;
    border: none;
    margin: 10px 0px 10px 0px;
}

QScrollBar::handle:vertical {
    background-color: %(primary.bright)s;
    min-height: 20px;
    margin: 1px 0px 1px 1px;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    background-color: %(background.bright)s;
    border-left: 1px solid %(background.bright)s;
    margin: 0px 0px 0px 1px;
    height: 10px;
    width: 10px;
}

QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: none;
}

QScrollBar::sub-line:vertical {
    image: url(%(res)s/chevron_up.svg);
    subcontrol-position: top;
    subcontrol-origin: margin;
}

QScrollBar::add-line:vertical {
    image: url(%(res)s/chevron_down.svg);
    subcontrol-position: bottom;
    subcontrol-origin: margin;
}
"""


"""
QToolTip, QTextEdit, QLineEdit {
    border: 1px solid %(border.bright)s;
    background-color: %(background.bright)s;
}

QComboBox {
    border: 1px solid %(border.bright)s;
    padding: 2px;
}

QComboBox::drop-down {
    border: none;
}

QComboBox::down-arrow {
    image: url(%(res)s/down_arrow_dim.png);
}

QComboBox::down-arrow:on,
QComboBox::down-arrow:hover,
QComboBox::down-arrow:focus {
    image: url(%(res)s/down_arrow.png);
}

QAbstractSpinBox {
    border: 1px solid %(border.bright)s;
}

QAbstractSpinBox:up-button
{
    background-color: transparent;
    subcontrol-origin: border;
    subcontrol-position: center right;
}

QAbstractSpinBox:down-button
{
    background-color: transparent;
    subcontrol-origin: border;
    subcontrol-position: center left;
}

QAbstractSpinBox::up-arrow,
QAbstractSpinBox::up-arrow:disabled,
QAbstractSpinBox::up-arrow:off {
    image: url(%(res)s/up_arrow_dim.png);
}

QAbstractSpinBox::up-arrow:hover
{
    image: url(%(res)s/up_arrow.png);
}

QAbstractSpinBox::down-arrow,
QAbstractSpinBox::down-arrow:disabled,
QAbstractSpinBox::down-arrow:off
{
    image: url(%(res)s/down_arrow_dim.png);
}

QAbstractSpinBox::down-arrow:hover
{
    image: url(%(res)s/down_arrow.png);
}

"""


"""
QSlider::groove:horizontal {
    background: %(background.bright)s;
    border: 1px solid %(border.bright)s;
    border-radius: 2px;
    height: 2px;
    margin: 2px 0;
}

QSlider::handle:horizontal {
    background: %(primary.bright)s;
    border: 1px solid %(border.bright)s;
    border-radius: 2px;
    width: 6px;
    height: 14px;
    margin: -8px 0;
}

QSlider::groove:vertical {
    background: %(background.bright)s;
    border: 1px solid %(border.bright)s;
    border-radius: 2px;
    width: 2px;
    margin: 0 0px;
}

QSlider::handle:vertical {
    background: %(primary.bright)s;
    border: 1px solid %(border.bright)s;
    border-radius: 2px;
    width: 14px;
    height: 6px;
    margin: 0 -8px;
}

QSlider:focus {
    border: none;
}

"""


def qss_to_f_string(qss_str, theme_cls):
    palette_str = {
        str(v): f"{{self.palette.{k}}}"
        for k, v in theme_cls.palette.__dict__.items()
    }
    qss_str = qss_str.replace("{", "{{").replace("}", "}}")
    qss_str = re.sub("([0-9]+)(px)", r'{px(\1)}', qss_str)  # 12px -> {px(12)}

    for hsl_str, replacement in palette_str.items():
        qss_str = qss_str.replace(hsl_str, replacement)

    return qss_str
