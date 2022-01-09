
from ..core import SuiteOp, SuiteCtx, InstalledPackages, Storage
from ._vendor.Qt5 import QtCore


class Controller(QtCore.QObject):
    context_added = QtCore.Signal(SuiteCtx)
    context_resolved = QtCore.Signal(str, SuiteCtx)
    context_dropped = QtCore.Signal(str)
    context_renamed = QtCore.Signal(str, str)
    context_reordered = QtCore.Signal(list)
    tools_updated = QtCore.Signal(list)
    pkg_scan_started = QtCore.Signal()
    pkg_families_scanned = QtCore.Signal(list)
    pkg_versions_scanned = QtCore.Signal(list)
    pkg_scan_ended = QtCore.Signal()
    storage_scan_started = QtCore.Signal()
    storage_scanned = QtCore.Signal(str, list)
    storage_scan_ended = QtCore.Signal()

    def __init__(self, state):
        super(Controller, self).__init__()

        self._sop = SuiteOp()
        self._sto = Storage()
        self._pkg = InstalledPackages()
        self._state = state

    def on_add_context_clicked(self, name):
        self.add_context(name)

    def on_rename_context_clicked(self, name, new_name):
        self.rename_context(name, new_name)

    def on_drop_context_clicked(self, name):
        self.drop_context(name)

    def on_context_item_moved(self, names):
        self.reorder_contexts(names)

    def on_context_prefix_changed(self, name, prefix):
        self.set_context_prefix(name, prefix)

    def on_context_suffix_changed(self, name, suffix):
        self.set_context_suffix(name, suffix)

    def on_tool_alias_changed(self, name, tool, alias):
        self.set_tool_alias(name, tool, alias)

    def on_tool_hidden_changed(self, name, tool, hidden):
        self.set_tool_hidden(name, tool, hidden)

    def on_resolve_context_clicked(self, name, requests):
        self.resolve_context(name, requests=requests)

    def on_installed_pkg_scan_clicked(self):
        self.scan_installed_packages()

    def add_context(self, name, requests=None):
        requests = requests or []
        ctx = self._sop.add_context(name, requests=requests)
        self.context_added.emit(ctx)
        if requests:
            self._tools_updated()

    def rename_context(self, name, new_name):
        self._sop.update_context(name, new_name=new_name)
        self.context_renamed.emit(name, new_name)
        self._tools_updated()

    def drop_context(self, name):
        self._sop.drop_context(name)
        self.context_dropped.emit(name)
        self._tools_updated()

    def reorder_contexts(self, new_order):
        self._sop.reorder_contexts(new_order)
        self.context_reordered.emit(new_order)
        self._tools_updated()

    def set_context_prefix(self, name, prefix):
        self._sop.update_context(name, prefix=prefix)
        self._tools_updated()

    def set_context_suffix(self, name, suffix):
        self._sop.update_context(name, suffix=suffix)
        self._tools_updated()

    def set_tool_alias(self, name, tool, alias):
        self._sop.update_context(name, tool_name=tool, new_alias=alias)
        self._tools_updated()

    def set_tool_hidden(self, name, tool, hidden):
        self._sop.update_context(name, tool_name=tool, set_hidden=hidden)
        self._tools_updated()

    def resolve_context(self, name, requests):
        ctx = self._sop.update_context(name, requests=requests)
        self.context_resolved.emit(name, ctx)
        self._tools_updated()

    def _tools_updated(self):
        self.tools_updated.emit(list(self._sop.iter_tools()))

    def scan_installed_packages(self):
        self.pkg_scan_started.emit()
        self._pkg.clear_caches()

        families = list(self._pkg.iter_families())
        self.pkg_families_scanned.emit(families)

        for family in families:
            versions = list(self._pkg.iter_versions(family.name, family.path))
            self.pkg_versions_scanned.emit(versions)

        self.pkg_scan_ended.emit()

    def scan_suite_storage(self):
        self.storage_scan_started.emit()

        for branch in self._sto.branches():
            self.storage_scanned.emit(
                branch,
                list(self._sto.iter_saved_suites(branch)),
            )

        self.storage_scan_ended.emit()
