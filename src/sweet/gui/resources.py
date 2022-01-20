
import os
from collections import OrderedDict as odict
from ._vendor.Qt5 import QtGui

dirname = os.path.dirname(__file__)
_cache = {}
_themes = odict()


def load_themes():
    _themes.clear()
    for theme in default_themes():
        _themes[theme["name"]] = theme


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

    source = theme["source"]
    keywords = theme.get("keywords", dict())

    if any(source.endswith(ext) for ext in [".css", ".qss"]):
        if not os.path.isfile(source):
            print("Theme stylesheet file not found: %s" % source)
            return
        else:
            with open(source) as f:
                css = f.read()
    else:
        # plain css code
        css = source

    _cache["_keywordsCache_"] = keywords

    return format_stylesheet(css)


def format_stylesheet(css):
    try:
        return css % _cache["_keywordsCache_"]
    except KeyError as e:
        print("Stylesheet format failed: %s" % str(e))
        return ""


def default_themes():
    Resources.load()
    return [
        {
            "name": "sweet-dark",
            "source": os.path.join(dirname, "sweet.qss"),
            "keywords": {
                "primary.focus": "#76654B",
                "primary.bright": "#654F3E",
                "primary.dim": "#493D35",

                "secondary.focus": "#4B6375",
                "secondary.bright": "#3E6166",
                "secondary.dim": "#36494A",

                "surface.bright": "#262626",
                "surface.dim": "#212121",

                "background.bright": "#1F1F1F",
                "background.dim": "#1D1D1D",

                "border.bright": "#191919",
                "border.dim": "#242424",

                "error.bright": "#C62828",
                "error.dim": "#891B1B",

                "warning.bright": "#DC9029",
                "warning.dim": "#B8843A",

                "on.bright.primary": "#212121",
                "on.bright.secondary": "#212121",
                "on.bright.surface": "#A49884",
                "on.bright.background": "#6F6350",
                "on.bright.error": "#FFFFFF",

                "on.dim.primary": "#39322D",
                "on.dim.secondary": "#4B403E",
                "on.dim.surface": "#4D4D4D",
                "on.dim.background": "#3F3F3F",
                "on.dim.error": "#9E9E9E",
            }
        },
        {
            "name": "sweet-light",
            "source": os.path.join(dirname, "sweet.qss"),
            "keywords": {
                "primary.focus": "#76654B",
                "primary.bright": "#654F3E",
                "primary.dim": "#493D35",

                "secondary.focus": "#4B6375",
                "secondary.bright": "#3E6166",
                "secondary.dim": "#36494A",

                "surface.bright": "#C8BFB2",
                "surface.dim": "#B0A798",

                "background.bright": "#B3AA9E",
                "background.dim": "#A0988D",

                "border.bright": "#917F6F",
                "border.dim": "#A08F89",

                "error.bright": "#C62828",
                "error.dim": "#891B1B",

                "warning.bright": "#DC9029",
                "warning.dim": "#B8843A",

                "on.bright.primary": "#212121",
                "on.bright.secondary": "#212121",
                "on.bright.surface": "#342C25",
                "on.bright.background": "#2C251F",
                "on.bright.error": "#FFFFFF",

                "on.dim.primary": "#39322D",
                "on.dim.secondary": "#4B403E",
                "on.dim.surface": "#4D4D4D",
                "on.dim.background": "#3F3F3F",
                "on.dim.error": "#9E9E9E",
            }
        },
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
