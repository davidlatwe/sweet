
from ..gui.vendor.Qt5 import QtCore
from ..core import SuiteOp


class Controller(QtCore.QObject):

    def __init__(self, state):
        super(Controller, self).__init__()
        self._sop = SuiteOp()  # or this should be in `state` ?
        self._state = state

    @property
    def state(self):
        return self._state
