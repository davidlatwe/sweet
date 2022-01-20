
from collections import OrderedDict as odict
from ._vendor.Qt5 import QtGui
from .style import BaseLightTheme, BaseDarkTheme

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
