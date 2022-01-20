
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
        background=HSL(0.00, 0.00, 87.84),          # Grey 300

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
            self.compose_styles()
            self._composed = self.qss.toString()
            self._composed += "\nQTabBar{qproperty-drawBase: 0;}\n"
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
            backgroundColor=self.palette.secondary,
            border="none",
            borderRadius="0px",
            minHeight="24px",
            padding="8px",
        )
        self.qss.QPushButton["hover"].setValues(
            backgroundColor=self.palette.primary,
        )
        self.qss.QPushButton["pressed"].setValues(
            backgroundColor=self.palette.primary_bright,
        )
        self.qss.QPushButton["focus"].setValues(
            border="none",
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
            image="url(:/icons/checkbox_unchecked)",
        )
        self.qss.QCheckBox["indicator"]["unchecked"]["disabled"].setValues(
            image="url(:/icons/checkbox_unchecked_dim)",
        )
        self.qss.QCheckBox["indicator"]["checked"].setValues(
            image="url(:/icons/checkbox_checked)",
        )
        self.qss.QCheckBox["indicator"]["checked"]["disabled"].setValues(
            image="url(:/icons/checkbox_checked_dim)",
        )
        self.qss.QCheckBox["indicator"]["indeterminate"].setValues(
            image="url(:/icons/checkbox_indeterminate)",
        )
        self.qss.QCheckBox["indicator"]["indeterminate"]["disabled"].setValues(
            image="url(:/icons/checkbox_indeterminate_dim)",
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
            image="url(:/icons/checkbox_checked)",
        )
        self.qss.QMenu["indicator"]["non-exclusive"]["unchecked"].setValues(
            image="url(:/icons/checkbox_unchecked)",
        )
        self.qss.QMenu["indicator"]["exclusive"]["checked"].setValues(
            image="url(:/icons/checkbox_checked)",
        )
        self.qss.QMenu["indicator"]["exclusive"]["unchecked"].setValues(
            image="url(:/icons/checkbox_unchecked)",
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
            border=f"1px solid {self.palette.on_surface}",
            padding="5px",
        )


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
