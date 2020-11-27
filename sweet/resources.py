
import os
from Qt5 import QtGui
from collections import OrderedDict as odict

dirname = os.path.dirname(__file__)
_cache = {}
_themes = odict()


def find(*paths):
    fname = os.path.join(dirname, "resources", *paths)
    fname = os.path.normpath(fname)  # Conform slashes and backslashes
    return fname.replace("\\", "/")  # Cross-platform compatibility


def load_themes():
    _themes.clear()
    for theme in default_themes():
        _themes[theme["name"]] = theme


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
    _load_fonts()
    res_root = os.path.join(dirname, "resources", "images").replace("\\", "/")
    return [
        {
            "name": "default-dark",
            "source": find("style.qss"),
            "keywords": {
                "prim": "#2E2C2C",
                "brightest": "#403E3D",
                "bright": "#383635",
                "base": "#2E2C2C",
                "dim": "#21201F",
                "dimmest": "#141413",
                "hover": "rgba(104, 182, 237, 60)",
                "highlight": "rgb(110, 191, 245)",
                "highlighted": "#111111",
                "outline": "rgba(10, 10, 10, 140)",
                "active": "silver",
                "inactive": "dimGray",
                "res": res_root,
            }
        },
    ]


def _load_fonts():
    """Load default fonts from resources"""
    _res_root = os.path.join(dirname, "resources").replace("\\", "/")

    font_root = os.path.join(_res_root, "fonts")
    fonts = [
        "opensans/OpenSans-Bold.ttf",
        "opensans/OpenSans-BoldItalic.ttf",
        "opensans/OpenSans-ExtraBold.ttf",
        "opensans/OpenSans-ExtraBoldItalic.ttf",
        "opensans/OpenSans-Italic.ttf",
        "opensans/OpenSans-Light.ttf",
        "opensans/OpenSans-LightItalic.ttf",
        "opensans/OpenSans-Regular.ttf",
        "opensans/OpenSans-Semibold.ttf",
        "opensans/OpenSans-SemiboldItalic.ttf",

        "jetbrainsmono/JetBrainsMono-Bold.ttf"
        "jetbrainsmono/JetBrainsMono-Bold-Italic.ttf"
        "jetbrainsmono/JetBrainsMono-ExtraBold.ttf"
        "jetbrainsmono/JetBrainsMono-ExtraBold-Italic.ttf"
        "jetbrainsmono/JetBrainsMono-ExtraLight.ttf"
        "jetbrainsmono/JetBrainsMono-ExtraLight-Italic.ttf"
        "jetbrainsmono/JetBrainsMono-Italic.ttf"
        "jetbrainsmono/JetBrainsMono-Light.ttf"
        "jetbrainsmono/JetBrainsMono-Light-Italic.ttf"
        "jetbrainsmono/JetBrainsMono-Medium.ttf"
        "jetbrainsmono/JetBrainsMono-Medium-Italic.ttf"
        "jetbrainsmono/JetBrainsMono-Regular.ttf"
        "jetbrainsmono/JetBrainsMono-SemiLight.ttf"
        "jetbrainsmono/JetBrainsMono-SemiLight-Italic.ttf"
    ]

    for font in fonts:
        path = os.path.join(font_root, font)
        QtGui.QFontDatabase.addApplicationFont(path)
