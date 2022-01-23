
from dataclasses import dataclass
import qstylizer.style


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
        on_secondary=HSL(0.00, 0.00, 25.88),        # Grey 800
        on_surface=HSL(200.00, 15.63, 62.35),       # Blue Grey 300
        on_background=HSL(200.00, 15.63, 62.35),    # Blue Grey 300
        on_error=HSL(0.00, 0.00, 12.94),            # Grey 900
        on_warning=HSL(0.00, 0.00, 12.94),          # Grey 900
    )

    def __init__(self):
        self._composed = None
        self.qss = qstylizer.style.StyleSheet()

    def style_sheet(self, refresh=False):
        if self._composed is None or refresh:
            self._composed = ""
            self.compose_styles()
            self._composed += self.qss.toString()
            self._composed += """
        QTabBar {qproperty-drawBase: 0;}
        QSplitterHandle:hover {} /*https://bugreports.qt.io/browse/QTBUG-13768*/
        """
        return self._composed

    def compose_styles(self):
        for name in self.__dir__():
            if name.startswith("_q_"):
                getattr(self, name)()

    def _q_global(self):
        self.qss.setValues(
            border="none",
            outline="none",
            fontFamily="Open Sans",
            color=self.palette.on_primary,  # text color
            borderColor=self.palette.background,
            backgroundColor=self.palette.background,
        )

    def _q_widget(self):
        self.qss.QWidget["focus"].setValues(
            border=f"1px solid {self.palette.on_surface * 1.5}",
        )
        self.qss.QWidget["disabled"].setValues(
            color=self.palette.on_background,
        )

    def _q_label(self):
        self.qss.QLabel.setValues(
            paddingTop="2px",
            paddingBottom="2px",
        )

    def _q_button(self):
        self.qss.QPushButton.setValues(
            backgroundColor=self.palette.background,
            border=f"1px solid {self.palette.on_background}",
            borderRadius="0px",
            minHeight="24px",
            padding="4px",
        )
        self.qss.QPushButton["hover"].setValues(
            backgroundColor=self.palette.background,
            border=f"1px solid {self.palette.primary}",
        )
        self.qss.QPushButton["pressed"].setValues(
            backgroundColor=self.palette.surface,
            border=f"1px dashed {self.palette.on_background}",
        )
        self.qss.QPushButton["focus"]["!hover"].setValues(
            backgroundColor=self.palette.background,
            border=f"1px solid {self.palette.on_background}",
            fontWeight="bold",
        )

    def _q_check_box(self):
        self.qss.QCheckBox.setValues(
            spacing="5px",
            marginBottom="2px",
        )
        self.qss.QCheckBox["focus"].setValues(
            border="none",
        )
        self.qss.QCheckBox["indicator"].setValues(
            width="15px",
            height="15px",
            backgroundColor=self.palette.background,
        )
        self.qss.QCheckBox["indicator"]["unchecked"].setValues(
            image="url(:/icons/checkbox_unchecked.png)",
        )
        self.qss.QCheckBox["indicator"]["unchecked"]["disabled"].setValues(
            image="url(:/icons/checkbox_unchecked_dim.png)",
        )
        self.qss.QCheckBox["indicator"]["checked"].setValues(
            image="url(:/icons/checkbox_checked.png)",
        )
        self.qss.QCheckBox["indicator"]["checked"]["disabled"].setValues(
            image="url(:/icons/checkbox_checked_dim.png)",
        )
        self.qss.QCheckBox["indicator"]["indeterminate"].setValues(
            image="url(:/icons/checkbox_indeterminate.png)",
        )
        self.qss.QCheckBox["indicator"]["indeterminate"]["disabled"].setValues(
            image="url(:/icons/checkbox_indeterminate_dim.png)",
        )

    def _q_menu(self):
        self.qss.QMenu.setValues(
            paddingTop="2px",
            paddingBottom="2px",
            backgroundColor=self.palette.surface,
            border=f"1px solid transparent",
        )
        self.qss.QMenu["item"].setValues(
            padding="5px 16px 5px 16px",
            marginLeft="5px",
        )
        self.qss.QMenu["item"]["!selected"].setValues(
            color=self.palette.on_surface,
        )
        self.qss.QMenu["item"]["selected"].setValues(
            color=self.palette.on_secondary,
            backgroundColor=self.palette.secondary,
        )
        self.qss.QMenu["item"]["disabled"].setValues(
            color=self.palette.surface,
        )
        self.qss.QMenu["indicator"].setValues(
            width="12px",
            height="12px",
            marginLeft="4px",
        )
        self.qss.QMenu["indicator"]["non-exclusive"]["checked"].setValues(
            image="url(:/icons/checkbox_checked.png)",
        )
        self.qss.QMenu["indicator"]["non-exclusive"]["unchecked"].setValues(
            image="url(:/icons/checkbox_unchecked.png)",
        )
        self.qss.QMenu["indicator"]["exclusive"]["checked"].setValues(
            image="url(:/icons/checkbox_checked.png)",
        )
        self.qss.QMenu["indicator"]["exclusive"]["unchecked"].setValues(
            image="url(:/icons/checkbox_unchecked.png)",
        )

    def _q_frame(self):
        # separator line
        self.qss[".QFrame"].setValues(
            color=self.palette.on_background,
        )

    def _q_tabs(self):
        self.qss.QTabWidget.setValues(
            border="none",
        )
        self.qss.QTabWidget["pane"].setValues(
            border=f"1px solid {self.palette.on_surface}",
            borderRadius="0px",
            padding="3px",
        )

        self.qss.QTabBar["focus"].setValues(
            border="0px transparent",
        )
        self.qss.QTabBar["tab"].setValues(
            backgroundColor=self.palette.surface,
            border=f"1px solid {self.palette.on_surface}",
            padding="5px",
        )

        self.qss.QTabBar["tab"]["!selected"].setValues(
            color=self.palette.on_background,
            backgroundColor=self.palette.background,
        )

        self.qss.QTabBar["tab"]["!selected"]["hover"].setValues(
            color=self.palette.on_primary,
            backgroundColor=self.palette.primary,
        )

        # note: "border: none" does not equal to "border: 1px solid transparent",
        #          there still 1px difference and may affect text position in tab

        self.qss.QTabBar["tab"]["top"].setValues(
            borderRight="none",
            borderBottom="none",
        )

        self.qss.QTabBar["tab"]["top"]["only-one"].setValues(
            borderRight=f"1px solid {self.palette.on_surface}",
        )
        self.qss.QTabBar["tab"]["top"]["last"].setValues(
            borderRight=f"1px solid {self.palette.on_surface}",
        )

        self.qss.QTabBar["tab"]["bottom"].setValues(
            borderRight="none",
            borderTop="none",
        )

        self.qss.QTabBar["tab"]["bottom"]["only-one"].setValues(
            borderRight=f"1px solid {self.palette.on_surface}",
        )
        self.qss.QTabBar["tab"]["bottom"]["last"].setValues(
            borderRight=f"1px solid {self.palette.on_surface}",
        )

        self.qss.QTabBar["tab"]["left"].setValues(
            color=self.palette.on_background,
            backgroundColor=self.palette.on_background,
            border=f"1px solid {self.palette.on_surface}",
            borderBottom="1px solid transparent",
            padding="8px",
        )

        self.qss.QTabBar["tab"]["left"]["next-selected"].setValues(
            borderTop=f"1px solid {self.palette.on_surface}",
        )

        self.qss.QTabBar["tab"]["left"]["selected"].setValues(
            color=self.palette.on_surface,
            backgroundColor=self.palette.surface,
            border=f"1px solid {self.palette.on_surface}",
            borderRight="1px solid transparent",
        )

        self.qss.QTabBar["tab"]["left"]["previous-selected"].setValues(
            borderTop="1px solid transparent",
        )

        self.qss.QTabBar["tab"]["left"]["!selected"].setValues(
            color=self.palette.on_background,
            backgroundColor=self.palette.background,
            borderRight=f"1px solid {self.palette.on_surface}",
            marginLeft="3px",
            paddingLeft="5px",
        )

        self.qss.QTabBar["tab"]["left"]["last"]["!selected"].setValues(
            borderBottom=f"1px solid {self.palette.on_surface}",
        )

        self.qss.QTabBar["tab"]["left"]["last"]["selected"].setValues(
            borderBottom=f"1px solid {self.palette.on_surface}",
        )

        self.qss.QTabBar["tab"]["left"]["!selected"]["hover"].setValues(
            color=self.palette.on_primary,
            backgroundColor=self.palette.primary,
        )

        _ = dict(
            color=self.palette.on_background,
            backgroundColor=self.palette.background,
            border=f"1px solid {self.palette.background}",
            borderRight=f"1px solid {self.palette.on_surface}",
            borderBottom="1px solid transparent",
            marginLeft="3px",
            paddingLeft="5px",
        )
        self.qss.QTabBar["tab"]["left"]["disabled"].setValues(**_)
        self.qss.QTabBar["tab"]["left"]["disabled"]["selected"].setValues(**_)

        self.qss.QTabBar["tab"]["left"]["disabled"]["previous-selected"].setValues(
            borderTop=f"1px solid {self.palette.on_surface}",
        )

        self.qss.QTabBar["tab"]["left"]["disabled"]["last"].setValues(
            borderBottom=f"1px solid {self.palette.background}",
        )

        self.qss.QTabBar["scroller"].setValues(
            width="24px",
        )

        self.qss["QTabBar QToolButton"].setValues(
            color=self.palette.on_surface,
            backgroundColor=self.palette.surface,
            border=f"1px solid {self.palette.on_surface}",
        )

        self.qss["QTabBar QToolButton"]["disabled"].setValues(
            color=self.palette.on_background,
            backgroundColor=self.palette.background,
            border=f"1px solid {self.palette.on_background}",
        )

    def _q_splitter(self):
        self.qss.QSplitter["handle"]["vertical"].setValues(
            height="0px",  # Height, not Width !
            margin="4px",
            padding="-3px",
            backgroundColor="transparent",
            border=f"1px dotted {self.palette.on_primary}",
        )
        self.qss.QSplitter["handle"]["vertical"]["hover"].setValues(
            backgroundColor="transparent",
            border=f"1px dotted {self.palette.on_surface}",
        )
        self.qss.QSplitter["handle"]["horizontal"].setValues(
            width="0px",  # NOT Height, it's Width !
            margin="4px",
            padding="-3px",
            backgroundColor="transparent",
            border=f"1px dotted {self.palette.on_primary}",
        )
        self.qss.QSplitter["handle"]["horizontal"]["hover"].setValues(
            backgroundColor="transparent",
            border=f"1px dotted {self.palette.on_surface}",
        )

    def _q_header(self):
        self.qss.QHeaderView.setValues(
            border="none",
            fontWeight="normal",
        )

        self.qss.QHeaderView["section"].setValues(
            padding="0px",
            paddingLeft="5px",
            paddingRight="5px",
            paddingTop="5px",
            background=self.palette.background,
            borderTop="none",
            borderBottom=f"1px solid {self.palette.on_secondary}",
            borderLeft="none",
            borderRight="none",
        )

        self.qss.QHeaderView["section"]["first"].setValues(
            borderLeft="none",
        )

        self.qss.QHeaderView["section"]["last"].setValues(
            borderRight="none",
        )

        self.qss.QHeaderView["down-arrow"].setValues(
            image="url(:/icons/chevron_down.svg)",
            subcontrolPosition="top center",
            height="8px",
            width="8px",
        )

        self.qss.QHeaderView["up-arrow"].setValues(
            image="url(:/icons/chevron_up.svg)",
            subcontrolPosition="top center",
            height="8px",
            width="8px",
        )

    def _q_tree_view(self):
        self.qss["QAbstractItemView"].setValues(
            showDecorationSelected="1",  # highlight the decoration (branch) !
            backgroundColor=self.palette.background,
            alternateBackgroundColor=self.palette.background,
            border="none",
            selectionColor=self.palette.on_primary,
            selectionBackgroundColor=self.palette.primary,
        )
        self.qss["QAbstractItemView"]["focus"].setValues(
            border="none",
        )

        self.qss["QAbstractItemView"]["item"]["selected"]["active"].setValues(
            backgroundColor=self.palette.secondary,
        )
        self.qss["QAbstractItemView"]["item"]["selected"]["!focus"].setValues(
            backgroundColor=self.palette.secondary,
        )

        self.qss["QAbstractItemView"]["item"]["hover"].setValues(
            color=self.palette.on_primary,
            backgroundColor=self.palette.primary,
        )
        self.qss["QAbstractItemView"]["item"]["hover"]["selected"].setValues(
            color=self.palette.on_primary,
            backgroundColor=self.palette.primary,
        )

        self.qss.QTreeView["branch"]["has-children"]["!has-siblings"]["closed"].setValues(
            image="url(:/icons/caret-right-fill.svg)",
        )
        self.qss.QTreeView["branch"]["closed"]["has-children"]["has-siblings"].setValues(
            image="url(:/icons/caret-right-fill.svg)",
        )

        self.qss.QTreeView["branch"]["open"]["has-children"]["!has-siblings"].setValues(
            image="url(:/icons/caret-down-fill.svg)",
        )
        self.qss.QTreeView["branch"]["open"]["has-children"]["has-siblings"].setValues(
            image="url(:/icons/caret-down-fill.svg)",
        )

        self.qss.QTreeView["branch"]["has-children"]["!has-siblings"]["closed"]["hover"].setValues(
            image="url(:/icons/caret-right-fill-on.svg)",
        )
        self.qss.QTreeView["branch"]["closed"]["has-children"]["has-siblings"]["hover"].setValues(
            image="url(:/icons/caret-right-fill-on.svg)",
        )

        self.qss.QTreeView["branch"]["open"]["has-children"]["!has-siblings"]["hover"].setValues(
            image="url(:/icons/caret-down-fill-on.svg)",
        )
        self.qss.QTreeView["branch"]["open"]["has-children"]["has-siblings"]["hover"].setValues(
            image="url(:/icons/caret-down-fill-on.svg)",
        )

        self.qss.QTreeView["branch"]["selected"].setValues(
            backgroundColor=self.palette.secondary,
        )

        self.qss.QTreeView["branch"]["hover"].setValues(
            backgroundColor=self.palette.primary
        )

    def _q_dialog(self):
        self.qss["#AcceptButton"].setValues(
            icon="url(:/icons/check-ok.svg)",
        )
        self.qss["#CancelButton"].setValues(
            icon="url(:/icons/x.svg)",
        )

    def _q_installed_packages(self):
        self.qss["#PackageView"].setValues(
            backgroundColor=self.palette.background,
        )
        self.qss["#PackagePage"].setValues(
            backgroundColor=self.palette.background,
            border=f"1px solid {self.palette.on_surface}",
            borderLeft="none",
        )
        self.qss["#PackageSide"].setValues(
            backgroundColor="transparent",
            border="none",
            borderRight=f"1px solid {self.palette.on_surface}",
        )

    def _q_context_buttons(self):
        # qstylilzer bug:
        #   AttributeError: 'PseudoStateRule' object has no attribute 'icon'
        #
        # also:
        #   property `icon` is available since 5.15. (only for QPushButton)
        #   https://doc.qt.io/qt-5/stylesheet-reference.html#icon
        #
        self._composed += """
        #ContextResolveOpBtn {
            icon: url(:/icons/lightning-fill-dim.svg);
        }
        #ContextResolveOpBtn:hover {
            icon: url(:/icons/lightning-fill.svg);
        }
        #ContextAddOpBtn {
            icon: url(:/icons/plus.svg);
        }
        #ContextAddOpBtn:hover {
            icon: url(:/icons/plus.svg);
        }
        #ContextRemoveOpBtn {
            icon: url(:/icons/trash-fill-dim.svg);
        }
        #ContextRemoveOpBtn:hover {
            icon: url(:/icons/trash-fill.svg);
        }
        """

    def _q_suite_bar(self):
        self._composed += """
        #SuiteNameEdit {
            font-size: 24px;
        }
        #SuiteSaveButton {
            min-height:24px;
            min-width: 80px;
            icon: url(:/icons/egg-fried-dim.svg);
        }
        #SuiteSaveButton:hover {
            icon: url(:/icons/egg-fried.svg);
        }
        #SuiteNewButton {
            min-height:24px;
            min-width: 80px;
            icon: url(:/icons/egg-fill-dim.svg);
        }
        #SuiteNewButton:hover {
            icon: url(:/icons/egg-fill.svg);
        }
        """

    def _q_requests(self):
        self._composed += """
        #RequestTextEdit,
        #RequestTableEdit {
            font-family: "JetBrains Mono";
        }
        """

    def _q_tool_view(self):
        self._composed += """
        #ToolsView::item {
            padding-left: 4px;
        }
        #ToolsView::indicator:unchecked {
            image: url(:icons/toggle-off.svg);
        }
        #ToolsView::indicator:unchecked:hover {
            image: url(:icons/toggle-off-bright.svg);
        }
        #ToolsView::indicator:unchecked:disabled {
            image: url(:icons/toggle-off-dim.svg);
        }
        #ToolsView::indicator:checked {
            image: url(:icons/toggle-on.svg);
        }
        #ToolsView::indicator:checked:hover {
            image: url(:icons/toggle-on-bright.svg);
        }
        #ToolsView::indicator:checked:disabled {
            image: url(:icons/toggle-on-dim.svg);
        }
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


"""
#PackageTreeView::item{
    padding: 5px 1px;
    border: 0px;
}

#PackageTreeView::item:selected{
    padding: 5px 1px;
    border: 0px;
}

#PackageTreeView::indicator:unchecked {
    image: url(%(res)s/checkbox_unchecked.png);
}

#PackageTreeView::indicator:unchecked:disabled {
    image: url(%(res)s/checkbox_unchecked_dim.png);
}

#PackageTreeView::indicator:checked {
    image: url(%(res)s/checkbox_checked.png);
}

#PackageTreeView::indicator:checked:disabled {
    image: url(%(res)s/checkbox_checked_dim.png);
}

#PackageTreeView::indicator:indeterminate {
    image: url(%(res)s/checkbox_indeterminate.png);
}

#PackageTreeView::indicator:indeterminate:disabled {
    image: url(%(res)s/checkbox_indeterminate_dim.png);
}

"""
