
import logging
import inspect
import functools
from itertools import groupby
from rez.resolved_context import ResolvedContext
from ..core import (
    SuiteOp,
    InstalledPackages,
    Storage,
    SuiteCtx,
    SavedSuite,
    PkgFamily,
    PkgVersion,
)
from ._vendor.Qt5 import QtCore
from .widgets import BusyWidget


log = logging.getLogger("sweet")


def _defer(on_time=500):
    """A decorator for deferring Controller function call

    :param on_time: The time to wait before the function runs (msec)
    :type on_time: int
    :return:
    """
    def decorator(func):
        @functools.wraps(func)
        def decorated(*args, **kwargs):
            self = args[0]
            fn_name = func.__name__
            self._sender[fn_name] = QtCore.QObject.sender(self)  # real sender
            if fn_name not in self._timers:
                # init timer
                d = {
                    "timer": QtCore.QTimer(self),
                    "args": tuple(),
                    "kwargs": dict(),
                }
                self._timers[fn_name] = d

                def on_timeout():
                    func(*d["args"], **d["kwargs"])
                    self._sender.pop(fn_name, None)  # cleanup

                d["timer"].timeout.connect(on_timeout)
                d["timer"].setSingleShot(True)

            d = self._timers[fn_name]
            d["args"] = args
            d["kwargs"] = kwargs
            d["timer"].start(kwargs.get("on_time") or on_time)

        return decorated

    return decorator


def _thread(name, blocks=None):
    """A decorator for running Controller functions in worker thread

    :param name: Thread name
    :param blocks: A tuple of `BusyWidget` object name strings
    :type name: str
    :type blocks: tuple[str] or None
    :return:
    """
    # todo:
    #  closing app while thread running ->
    #   QThread: Destroyed while thread is still running

    def decorator(func):
        @functools.wraps(func)
        def decorated(*args, **kwargs):
            self = args[0]  # type: Controller
            fn_name = func.__name__

            if name not in self._thread:
                self._thread[name] = Thread(self)
            thread = self._thread[name]

            if thread.isRunning():
                log.info(f"Thread {name!r} is busy, can't process {fn_name!r}.")
                return

            blocks_ = blocks or []
            busy_widgets = [
                w for w in BusyWidget.instances() if w.objectName() in blocks_
            ]  # type: list[BusyWidget]

            for widget in busy_widgets:
                widget.set_overwhelmed(True)

            def on_finished():
                for w in busy_widgets:
                    w.set_overwhelmed(False)
                thread.finished.disconnect(on_finished)
                log.info(f"Thread {name!r} finished {fn_name!r}.")

            thread.finished.connect(on_finished)

            log.info(f"Thread {name!r} is about to run {fn_name!r}.")
            thread.set_job(func, *args, **kwargs)
            thread.start()

        return decorated
    return decorator


class Controller(QtCore.QObject):
    """Application controller
    """
    suite_newed = QtCore.Signal()
    suite_saved = QtCore.Signal(SavedSuite)
    suite_save_failed = QtCore.Signal(str)
    suite_loaded = QtCore.Signal(str, str, str, str)
    context_added = QtCore.Signal(SuiteCtx)
    context_resolved = QtCore.Signal(str, object)
    context_dropped = QtCore.Signal(str)
    context_renamed = QtCore.Signal(str, str)
    context_reordered = QtCore.Signal(list)
    resolve_failed = QtCore.Signal()
    tools_updated = QtCore.Signal(list)
    pkg_scan_started = QtCore.Signal()
    pkg_families_scanned = QtCore.Signal(list)
    pkg_versions_scanned = QtCore.Signal(list)
    pkg_scan_ended = QtCore.Signal()
    storage_scan_started = QtCore.Signal()
    storage_scanned = QtCore.Signal(list)
    storage_scan_ended = QtCore.Signal()
    status_message = QtCore.Signal(str)

    def __init__(self):
        super(Controller, self).__init__(parent=None)

        self._sop = SuiteOp()
        self._sto = Storage()
        self._pkg = InstalledPackages()
        self._dirty = False
        self._timers = dict()
        self._sender = dict()
        self._thread = dict()  # type: dict[str, Thread]

        _defer(on_time=500)(Controller.scan_suite_storage)(self)
        _defer(on_time=500)(Controller.scan_installed_packages)(self)
        _defer(on_time=600)(Controller.new_suite)(self)

    def sender(self):
        """Internal use. To preserve real signal sender for decorated method."""
        f = inspect.stack()[1].function
        return self._sender.pop(f, super(Controller, self).sender())

    @QtCore.Slot()  # noqa
    def on_suite_dirty_asked(self):
        self.sender().answer_dirty(self._dirty)

    @QtCore.Slot()  # noqa
    def on_storage_branches_asked(self):
        self.sender().answer_branches(self._sto.branches())

    @QtCore.Slot()  # noqa
    def on_suite_new_clicked(self):
        self.new_suite()

    @QtCore.Slot(str, str, bool)  # noqa
    def on_suite_load_clicked(self, name, branch, as_import):
        self.load_suite(name, branch, as_import)

    @QtCore.Slot(str, str, str)  # noqa
    def on_suite_save_clicked(self, branch, name, description):
        self.save_suite(branch, name, description)

    @QtCore.Slot(str)  # noqa
    def on_add_context_clicked(self, name):
        self.add_context(name)

    @QtCore.Slot(str, str)  # noqa
    def on_rename_context_clicked(self, name, new_name):
        self.rename_context(name, new_name)

    @QtCore.Slot(str)  # noqa
    def on_drop_context_clicked(self, name):
        self.drop_context(name)

    @QtCore.Slot(list)  # noqa
    def on_context_item_moved(self, names):
        self.reorder_contexts(names)

    @QtCore.Slot(str, str)  # noqa
    @_defer(on_time=400)
    def on_context_prefix_changed(self, name, prefix):
        self.set_context_prefix(name, prefix)

    @QtCore.Slot(str, str)  # noqa
    @_defer(on_time=400)
    def on_context_suffix_changed(self, name, suffix):
        self.set_context_suffix(name, suffix)

    @QtCore.Slot(str, str, str)  # noqa
    @_defer(on_time=400)
    def on_tool_alias_changed(self, name, tool, alias):
        self.set_tool_alias(name, tool, alias)

    @QtCore.Slot(str, str, bool)  # noqa
    @_defer(on_time=50)
    def on_tool_hidden_changed(self, name, tool, hidden):
        self.set_tool_hidden(name, tool, hidden)

    @QtCore.Slot(str, list)  # noqa
    def on_resolve_context_clicked(self, name, requests):
        self.resolve_context(name, requests=requests)

    @QtCore.Slot()  # noqa
    def on_installed_pkg_scan_clicked(self):
        self.scan_installed_packages()

    @_thread(name="suiteOp", blocks=("SuitePage",))
    def add_context(self, name, context=None):
        _context = context or self._sop.resolve_context([])
        ctx = self._sop.add_context(name, _context)
        self.context_added.emit(ctx)
        if context is not None:
            self._tools_updated()
        self._dirty = True

    @_thread(name="suiteOp", blocks=("SuitePage",))
    def rename_context(self, name, new_name):
        self._sop.update_context(name, new_name=new_name)
        self.context_renamed.emit(name, new_name)
        self._tools_updated()

    @_thread(name="suiteOp", blocks=("SuitePage",))
    def drop_context(self, name):
        self._sop.drop_context(name)
        self.context_dropped.emit(name)
        self._tools_updated()

    @_thread(name="suiteOp", blocks=("SuitePage",))
    def reorder_contexts(self, new_order):
        self._sop.reorder_contexts(new_order)
        self.context_reordered.emit(new_order)
        self._tools_updated()

    @_thread(name="suiteOp", blocks=("SuitePage",))
    def set_context_prefix(self, name, prefix):
        self._sop.update_context(name, prefix=prefix)
        self._tools_updated()

    @_thread(name="suiteOp", blocks=("SuitePage",))
    def set_context_suffix(self, name, suffix):
        self._sop.update_context(name, suffix=suffix)
        self._tools_updated()

    @_thread(name="suiteOp", blocks=("SuitePage",))
    def set_tool_alias(self, name, tool, alias):
        self._sop.update_context(name, tool_name=tool, new_alias=alias)
        self._tools_updated()

    @_thread(name="suiteOp", blocks=("SuitePage",))
    def set_tool_hidden(self, name, tool, hidden):
        self._sop.update_context(name, tool_name=tool, set_hidden=hidden)
        self._tools_updated()

    @_thread(name="suiteOp", blocks=("SuitePage",))
    def resolve_context(self, name, requests):
        context = self._sop.resolve_context(requests)
        self.context_resolved.emit(name, context)
        if context.success:
            self._sop.update_context(name, context=context)
            self._tools_updated()
        else:
            self.resolve_failed.emit()

    def _tools_updated(self):
        self._dirty = True
        self.tools_updated.emit(list(self._sop.iter_tools()))

    @_thread(name="suiteOp", blocks=("SuitePage",))
    def new_suite(self):
        self._reset_suite()
        # add a default context 'new'
        ctx = self._sop.add_context("new", self._sop.resolve_context([]))
        self.context_added.emit(ctx)

    @_thread(name="suiteOp", blocks=("SuitePage",))
    def save_suite(self, branch, name, description):
        path = self._sto.suite_path(branch, name)
        self._sop.set_description(description)
        try:
            self._sop.save(path)
        except Exception as e:
            self.suite_save_failed.emit(str(e))
        else:
            saved_suite = SavedSuite(
                name=name,
                branch=branch,
                path=path,
                suite=None,  # lazy load
            )
            self._dirty = False
            self.suite_saved.emit(saved_suite)

    @_thread(name="suiteOp", blocks=("SuitePage", "StoragePage"))
    def load_suite(self, name, branch, as_import):
        self._reset_suite()
        path = self._sto.suite_path(branch, name)
        self._sop.load(path, as_import)
        # loaded
        description = self._sop.get_description()
        load_path = self._sop.loaded_from() or ""

        for ctx in self._sop.iter_contexts(ascending=True):
            self.context_added.emit(ctx)
            self.context_resolved.emit(ctx.name, ctx.context)

        self._tools_updated()
        self._dirty = False
        self.suite_loaded.emit(name, description, load_path, branch)

    def _reset_suite(self):
        self._sop.reset()
        self._dirty = False
        self.suite_newed.emit()

    @_thread(name="scanPkg")
    def scan_installed_packages(self):
        ct = QtCore.QThread.currentThread()
        self.status_message.emit("Start scanning installed packages...")
        self.pkg_scan_started.emit()
        self._pkg.clear_caches()

        # it's also important to sort before `groupby`
        family_key = (lambda f: f.name.lower())
        all_families = sorted(
            self._pkg.iter_families(), key=family_key
        )  # type: list[PkgFamily]

        self.pkg_families_scanned.emit(all_families)

        grouped_families = [
            (k, list(ls)) for k, ls in groupby(all_families, key=family_key)
        ]

        _fm_count = len(grouped_families)
        _path_count = len(self._pkg.packages_path)
        self.status_message.emit(
            f"Found {_fm_count} families from {_path_count} locations."
        )

        _current = None
        for i, (key, same_families) in enumerate(grouped_families):
            # ensure versions that belongs to same family get emitted in one
            # batch.
            versions = []

            for family in same_families:
                if ct.isInterruptionRequested():  # could be long running proc
                    break
                name, location = family.name, family.location
                versions += list(
                    self._pkg.iter_versions(name, location)
                )  # type: list[PkgVersion]

            self.pkg_versions_scanned.emit(versions)
            self.status_message.emit(
                f"Finding versions for {_fm_count} families from {_path_count} "
                f"locations {'.' * (int(i / 50) % 5)}"
            )  # animated dots that also reflects the speed of the process.

        self.pkg_scan_ended.emit()
        self.status_message.emit("All installed packages scanned.")

    @_thread(name="scanSuite", blocks=("StoragePage",))
    def scan_suite_storage(self):
        ct = QtCore.QThread.currentThread()
        self.status_message.emit("Start scanning saved suites...")
        self.storage_scan_started.emit()

        for branch in self._sto.branches():
            if ct.isInterruptionRequested():  # could be long running proc
                break
            self.storage_scanned.emit(
                list(self._sto.iter_saved_suites(branch)),
            )

        self.storage_scan_ended.emit()
        self.status_message.emit("All saved suites scanned.")


class Thread(QtCore.QThread):
    
    def __init__(self, *args, **kwargs):
        super(Thread, self).__init__(*args, **kwargs)
        self._func = None
        self._args = None
        self._kwargs = None

    def set_job(self, func, *args, **kwargs):
        self._func = func
        self._args = args
        self._kwargs = kwargs

    def run(self):
        self._func(*self._args, **self._kwargs)
