
import functools
from itertools import groupby
from ..core import (
    SuiteOp,
    InstalledPackages,
    Storage,
    SuiteCtx,
    PkgFamily,
    PkgVersion,
)
from ._vendor.Qt5 import QtCore


def _defer(on_time=500):
    """Function call deferrer for class Controller
    """
    def decorator(func):
        @functools.wraps(func)
        def decorated(*args, **kwargs):
            self = args[0]
            name = func.__name__
            if name not in self._timers:
                # init timer
                d = {
                    "timer": QtCore.QTimer(self),
                    "args": tuple(),
                    "kwargs": dict(),
                }
                self._timers[name] = d

                def on_timeout():
                    func(*d["args"], **d["kwargs"])

                d["timer"].timeout.connect(on_timeout)
                d["timer"].setSingleShot(True)

            d = self._timers[name]
            d["args"] = args
            d["kwargs"] = kwargs
            d["timer"].start(kwargs.get("on_time") or on_time)

        return decorated

    return decorator


class Controller(QtCore.QObject):
    """Application controller
    """
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
        self._timers = dict()

        self.defer_scan_suite_storage()
        self.defer_scan_installed_packages()

    @_defer(on_time=500)
    def defer_scan_installed_packages(self):
        self.background_scan_installed_packages()

    @_defer(on_time=500)
    def defer_scan_suite_storage(self):
        self.background_scan_suite_storage()

    @QtCore.Slot()  # noqa
    def on_add_context_clicked(self, name):
        self.add_context(name)

    @QtCore.Slot()  # noqa
    def on_rename_context_clicked(self, name, new_name):
        self.rename_context(name, new_name)

    @QtCore.Slot()  # noqa
    def on_drop_context_clicked(self, name):
        self.drop_context(name)

    @QtCore.Slot()  # noqa
    def on_context_item_moved(self, names):
        self.reorder_contexts(names)

    @QtCore.Slot()  # noqa
    @_defer(on_time=400)
    def on_context_prefix_changed(self, name, prefix):
        self.set_context_prefix(name, prefix)

    @QtCore.Slot()  # noqa
    @_defer(on_time=400)
    def on_context_suffix_changed(self, name, suffix):
        self.set_context_suffix(name, suffix)

    @QtCore.Slot()  # noqa
    @_defer(on_time=400)
    def on_tool_alias_changed(self, name, tool, alias):
        self.set_tool_alias(name, tool, alias)

    @QtCore.Slot()  # noqa
    @_defer(on_time=200)
    def on_tool_hidden_changed(self, name, tool, hidden):
        self.set_tool_hidden(name, tool, hidden)

    @QtCore.Slot()  # noqa
    @_defer(on_time=200)
    def on_resolve_context_clicked(self, name, requests):
        self.resolve_context(name, requests=requests)

    @QtCore.Slot()  # noqa
    @_defer(on_time=200)
    def on_installed_pkg_scan_clicked(self):
        self.scan_installed_packages()

    def background_scan_installed_packages(self):
        thread = QtCore.QThread(self)
        thread.run = self.scan_installed_packages
        thread.start()

    def background_scan_suite_storage(self):
        thread = QtCore.QThread(self)
        thread.run = self.scan_suite_storage
        thread.start()

    # todo:
    #  1. quit thread on app exit
    #  2. process should check if interruption requested in loop.

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

        family_key = (lambda f: f.name.lower())

        all_families = sorted(
            self._pkg.iter_families(), key=family_key
        )  # type: list[PkgFamily]

        self.pkg_families_scanned.emit(all_families)

        _current = None
        for key, same_families in groupby(all_families, key=family_key):
            # ensure versions that belongs to same family get emitted in one
            # batch.
            versions = []

            for family in same_families:
                name, location = family.name, family.location

                versions += list(
                    self._pkg.iter_versions(name, location)
                )  # type: list[PkgVersion]

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
