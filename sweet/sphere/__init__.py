
import sys
from .view import SphereView
# from .model import PackageModel
from .. import lib, resources


self = sys.modules[__name__]
self.window = None


def show():
    resources.load_themes()
    qss = resources.load_theme()

    view_ = SphereView()
    # model_ = PackageModel()
    # view_.setModel(model_)
    # view_.reset(lib.scan())

    view_.setStyleSheet(qss)
    view_.show()

    self.window = view_
