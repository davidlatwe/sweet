
from ..core import SuiteOp, SuiteCtx
from .. import _rezapi as rez
from ._vendor.Qt5 import QtCore


class Controller(QtCore.QObject):
    context_added = QtCore.Signal(SuiteCtx)
    context_dropped = QtCore.Signal(str)

    def __init__(self, state):
        super(Controller, self).__init__()

        self._sop = SuiteOp()
        self._state = state

    def on_stack_added(self, name):
        self.add_context(name)

    def on_stack_dropped(self, names):
        for name in names:
            self.drop_context(name)

    def on_stack_reordered(self, names):
        self.reorder_contexts(names)

    def add_context(self, name, requests=None):
        requests = requests or []
        ctx = self._sop.add_context(name, requests=requests)
        self.context_added.emit(ctx)

    def drop_context(self, name):
        self._sop.drop_context(name)
        self.context_dropped.emit(name)

    def reorder_contexts(self, new_order):
        print(new_order)
        # self._sop.reorder_contexts(new_order)

    def iter_installed_packages(self, no_local=False):
        paths = None
        seen = dict()

        if no_local:
            paths = rez.config.nonlocal_packages_path

        for family in rez.iter_package_families(paths=paths):
            name = family.name
            path = family.resource.location
            path = "{}@{}".format(family.repository.name(), path)

            for package in rez.iter_packages(name, paths=[path]):
                qualified_name = package.qualified_name

                if qualified_name in seen:
                    seen[qualified_name]["locations"].append(path)
                    continue

                doc = {
                    "family": name,
                    "version": str(package.version),
                    "uri": package.uri,
                    "tools": package.tools or [],
                    "qualified_name": qualified_name,
                    "timestamp": package.timestamp,
                    "locations": [path],
                }
                seen[qualified_name] = doc

                yield doc
