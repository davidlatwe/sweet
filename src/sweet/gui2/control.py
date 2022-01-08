
from ..core import SuiteOp, SuiteCtx
from .. import _rezapi as rez
from ._vendor.Qt5 import QtCore


class Controller(QtCore.QObject):
    context_added = QtCore.Signal(SuiteCtx)
    context_dropped = QtCore.Signal(str)
    context_reordered = QtCore.Signal(list)
    context_renamed = QtCore.Signal(str, str)

    def __init__(self, state):
        super(Controller, self).__init__()

        self._sop = SuiteOp()
        self._state = state

    def on_add_context_clicked(self, name):
        self.add_context(name)

    def on_rename_context_clicked(self, name, new_name):
        self.rename_context(name, new_name)

    def on_drop_context_clicked(self, name):
        self.drop_context(name)

    def on_context_item_moved(self, names):
        self.reorder_contexts(names)

    def on_resolve_context_clicked(self, name, requests):
        self.resolve_context(name, requests=requests)

    def add_context(self, name, requests=None):
        requests = requests or []
        ctx = self._sop.add_context(name, requests=requests)
        self.context_added.emit(ctx)

    def rename_context(self, name, new_name):
        self._sop.update_context(name, new_name=new_name)
        self.context_renamed.emit(name, new_name)

    def drop_context(self, name):
        self._sop.drop_context(name)
        self.context_dropped.emit(name)

    def reorder_contexts(self, new_order):
        self._sop.reorder_contexts(new_order)
        self.context_reordered.emit(new_order)

    def resolve_context(self, name, requests):
        self._sop.update_context(name, requests=requests)
        # todo: emit resolved signal

    def iter_installed_packages(self):
        pass
