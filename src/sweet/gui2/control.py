
from ..gui.vendor.Qt5 import QtCore, QtGui
from ..core import SuiteOp, SuiteCtx


class Controller(QtCore.QObject):
    context_added = QtCore.Signal(SuiteCtx)

    def __init__(self, state):
        super(Controller, self).__init__()

        self._sop = SuiteOp()
        self._state = state

    def on_stack_added(self, name):
        self.add_context(name)

    def add_context(self, name, requests=None):
        requests = requests or []
        ctx = self._sop.add_context(name, requests=requests)
        self.context_added.emit(ctx)
