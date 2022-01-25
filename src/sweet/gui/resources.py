
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
    a: float = 100

    def __str__(self):
        return f"hsla({self.h}, {self.s}%, {self.l}%, {self.a}%)"

    def __mul__(self, other: float):
        self.l *= other
        self.l = 100 if self.l > 100 else self.l
        self.l = 0 if self.l < 0 else self.l
        return self

    def __add__(self, other: float):
        self.l += other
        self.l = 100 if self.l > 100 else self.l
        self.l = 0 if self.l < 0 else self.l
        return self

    @property
    def bright(self):
        return HSL(self.h, self.s, self.l) * 1.2

    @property
    def dimmed(self):
        return HSL(self.h, self.s, self.l) * 0.7

    @property
    def fade(self):
        return HSL(self.h, self.s, self.l, self.a * 0.4)


@dataclass
class Palette:
    # highlight colors
    primary: HSL
    secondary: HSL
    # base colors
    surface: HSL
    background: HSL
    border: HSL
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
        secondary=HSL(15.88, 15.32, 56.47),         # Brown 300

        surface=HSL(0.00, 0.00, 96.08),             # Grey 100
        background=HSL(0.00, 0.00, 98.04),          # Grey 50
        border=HSL(0.00, 0.00, 74.12),              # Grey 400

        error=HSL(11.95, 100.00, 43.33),            # Deep Orange A700
        warning=HSL(40.24, 100.00, 50.00),          # Amber A700

        on_primary=HSL(0.00, 0.00, 25.88),          # Grey 800
        on_secondary=HSL(0.00, 0.00, 25.89),        # Grey 800.01
        on_surface=HSL(0.00, 0.00, 25.90),          # Grey 800.02
        on_background=HSL(0.00, 0.00, 25.91),       # Grey 800.03
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
            color: {self.palette.on_background};  /* text color */
            border-color: {self.palette.border};
            background-color: {self.palette.background};
        }}
        """

    def _q_widget(self):
        return f"""

        QWidget:focus {{
            border: 1px solid {self.palette.border.bright};
        }}
        QWidget:disabled {{
            color: {self.palette.on_background.fade};
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
            border: 1px solid {self.palette.border};
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
            border: 1px dashed {self.palette.border.bright};
        }}
        QPushButton:focus:!hover {{
            background-color: {self.palette.background};
            border: 1px solid {self.palette.border};
            font-weight: bold;
        }}
        QPushButton:disabled {{
            background-color: {self.palette.background};
            border: 2px dashed {self.palette.border.fade};
            color: {self.palette.on_background.fade};
        }}

        """

    def _q_combo_box(self):
        return f"""
        QComboBox {{
            border: 1px solid {self.palette.border};
            padding: {px(2)};
        }}
        QComboBox::drop-down {{
            border: none;
            min-width: {px(36)};
        }}
        QComboBox::down-arrow,
        QComboBox::down-arrow:focus {{
            image: url(:/icons/chevron_left.svg);
        }}
        QComboBox::down-arrow:on,
        QComboBox::down-arrow:hover {{
            image: url(:/icons/chevron_down.svg);
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
            color: {self.palette.on_primary};
            background-color: {self.palette.primary};
        }}
        QMenu::item:disabled {{
            color: {self.palette.on_surface.fade};
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
            border: 1px solid {self.palette.border};
            border-radius: 0px;
            padding: {px(3)};
        }}

        QTabBar:focus {{
            border: 0px transparent;
        }}

        QTabBar::tab {{
            background-color: {self.palette.secondary.fade};
            border: 1px solid {self.palette.border};
            padding: {px(5)};
        }}
        QTabBar::tab:!selected {{
            color: {self.palette.on_background};
            background-color: {self.palette.background};
        }}
        QTabBar::tab:hover {{
            color: {self.palette.on_primary};
            background-color: {self.palette.primary};
        }}
        
        /* top */

        QTabBar::tab::top {{
            border-right: none;
            border-bottom: none;
        }}
        QTabBar::tab::top:only-one {{
            border-right: 1px solid {self.palette.border};
        }}
        QTabBar::tab::top:last {{
            border-right: 1px solid {self.palette.border};
        }}
        
        /* bottom */

        QTabBar::tab::bottom {{
            border-right: none;
            border-top: none;
        }}
        QTabBar::tab::bottom:only-one {{
            border-right: 1px solid {self.palette.border};
        }}
        QTabBar::tab::bottom:last {{
            border-right: 1px solid {self.palette.border};
        }}
        
        /* left */

        QTabBar::tab::left {{
            color: {self.palette.on_background};
            background-color: {self.palette.background};
            border: 1px solid {self.palette.border};
            border-bottom: 1px solid transparent;
            padding: {px(8)};
        }}
        QTabBar::tab::left:next-selected {{
            border-top: 1px solid {self.palette.border};
        }}
        QTabBar::tab::left:selected {{
            color: {self.palette.on_primary};
            background-color: {self.palette.primary};
            border: 1px solid {self.palette.border};
            border-right: 1px solid transparent;
        }}
        QTabBar::tab::left:previous-selected {{
            border-top: 1px solid transparent;
        }}
        QTabBar::tab::left:!selected {{
            color: {self.palette.on_background};
            background-color: {self.palette.background};
            border-right: 1px solid {self.palette.border};
            margin-left: {px(3)};
            padding-left: {px(5)};
        }}
        QTabBar::tab::left:last:!selected {{
            border-bottom: 1px solid {self.palette.border};
        }}
        QTabBar::tab::left:last:selected {{
            border-bottom: 1px solid {self.palette.border};
        }}
        QTabBar::tab::left:!selected:hover {{
            color: {self.palette.on_primary};
            background-color: {self.palette.primary};
        }}
        QTabBar::tab::left:disabled {{
            color: {self.palette.on_background.fade};
            background-color: {self.palette.background};
            border: 1px solid {self.palette.border.fade};
            border-right: 1px solid {self.palette.border.fade};
            border-bottom: 1px solid transparent;
            margin-left: {px(3)};
            padding-left: {px(5)};
        }}
        QTabBar::tab::left:disabled:selected {{
            color: {self.palette.on_background.fade};
            background-color: {self.palette.background};
            border: 1px solid {self.palette.border.fade};
            border-right: 1px solid {self.palette.border.fade};
            border-bottom: 1px solid transparent;
            margin-left: {px(3)};
            padding-left: {px(5)};
        }}
        QTabBar::tab::left:disabled:previous-selected {{
            border-top: 1px solid {self.palette.border.fade};
        }}
        QTabBar::tab::left:disabled:last {{
            border-bottom: 1px solid {self.palette.border.fade};
        }}
        
        /* right (not defined) */

        /* others */

        QTabBar::scroller {{
            width: {px(24).floor};
        }}
        QTabBar QToolButton {{
            color: {self.palette.on_surface};
            background-color: {self.palette.surface};
            border: 1px solid {self.palette.border};
        }}
        QTabBar QToolButton:disabled {{
            color: {self.palette.on_background};
            background-color: {self.palette.background};
            border: 1px solid {self.palette.border};
        }}
        
        """

    def _q_splitter(self):
        return f"""

        QSplitter::handle:vertical {{
            height: 0px;
            margin: {px(4)};
            padding: 1px;
            background-color: transparent;
            border: none;
            border-top: 2px dotted {self.palette.border};
        }}
        QSplitter::handle:vertical:hover {{
            background-color: transparent;
            border: none;
            border-top: 2px solid {self.palette.border};
        }}
        QSplitter::handle:horizontal {{
            width: 0px;
            margin: {px(4)};
            padding: 1px;
            background-color: transparent;
            border: none;
            border-left: 2px dotted {self.palette.border};
        }}
        QSplitter::handle:horizontal:hover {{
            background-color: transparent;
            border: none;
            border-left: 2px solid {self.palette.border};
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
            border-bottom: 1px solid {self.palette.on_background};
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
            alternate-background-color: {self.palette.background.bright};
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
            border: 1px solid {self.palette.border};
            border-left: none;
        }}
        #PackageSide {{
            background-color: transparent;
            border: none;
            border-right: 1px solid {self.palette.border};
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

    def _q_scroll_bar(self):
        return f"""
        
        QAbstractScrollArea {{
            background-color: {self.palette.background};
        }}
        
        QScrollBar:horizontal {{
            background-color: {self.palette.background};
            height: {px(16)};
            border: none;
            border-top: 1px solid {self.palette.border};
            margin: 0px {px(16)} 0px {px(16)};
        }}
        
        QScrollBar::handle:horizontal {{
            background-color: {self.palette.surface};
            min-width: {px(20)};
            margin: 1px 1px 0px 1px;
        }}
        
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
            /*background-color: {self.palette.surface};*/
            border-top: 1px solid {self.palette.border};
            margin: 1px 0px 0px 0px;
            height: {px(16)};
            width: {px(16)};
        }}
        
        QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
            background: none;
        }}
        
        QScrollBar::sub-line:horizontal {{
            image: url(:/icons/chevron_left.svg);
            subcontrol-position: left;
            subcontrol-origin: margin;
        }}
        
        QScrollBar::add-line:horizontal {{
            image: url(:/icons/chevron_right.svg);
            subcontrol-position: right;
            subcontrol-origin: margin;
        }}
        
        
        QScrollBar:vertical {{
            background-color: {self.palette.background};
            width: {px(16)};
            border: none;
            border-left: 1px solid {self.palette.border};
            margin: {px(16)} 0px {px(16)} 0px;
        }}
        
        QScrollBar::handle:vertical {{
            background-color: {self.palette.surface};
            min-height: {px(20)};
            margin: 1px 0px 1px 1px;
        }}
        
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            /*background-color: {self.palette.surface};*/
            border-left: 1px solid {self.palette.border};
            margin: 0px 0px 0px 1px;
            height: {px(16)};
            width: {px(16)};
        }}
        
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
            background: none;
        }}
        
        QScrollBar::sub-line:vertical {{
            image: url(:/icons/chevron_up.svg);
            subcontrol-position: top;
            subcontrol-origin: margin;
        }}
        
        QScrollBar::add-line:vertical {{
            image: url(:/icons/chevron_down.svg);
            subcontrol-position: bottom;
            subcontrol-origin: margin;
        }}

        """

    def _q_others(self):
        return f"""
        
        #ButtonBelt QPushButton {{
            max-width: {px(18)};
            max-height: {px(18)};
            min-width: {px(18)};
            min-height: {px(18)};
            padding: {px(2)};
            border: none;
            background-color: transparent;
        }}
        
        #DocStrings {{
            color: {self.palette.on_background.fade};
        }}

        """


class BaseDarkTheme(BaseLightTheme):
    name = "sweet-dark"
    palette = Palette(
        primary=HSL(150.78, 100.00, 45.10),         # Green A400
        secondary=HSL(122.58, 15.97, 35.51),        # Green 600 (dimmed)

        surface=HSL(0.00, 0.00, 38.04),             # Grey 700
        background=HSL(0.00, 0.00, 12.94),          # Grey 900
        border=HSL(0.00, 0.00, 25.88),              # Grey 800

        error=HSL(11.95, 100.00, 43.33),            # Deep Orange A700
        warning=HSL(40.24, 100.00, 50.00),          # Amber A700

        on_primary=HSL(0.00, 0.00, 12.94),          # Grey 900
        on_secondary=HSL(0.00, 0.00, 25.90),        # Grey 800.02
        on_surface=HSL(0.00, 0.00, 38.05),          # Grey 700.01
        on_background=HSL(0.00, 0.00, 61.97),       # Grey 500.01
        on_error=HSL(0.00, 0.00, 12.95),            # Grey 900.01
        on_warning=HSL(0.00, 0.00, 12.96),          # Grey 900.02
    )


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
