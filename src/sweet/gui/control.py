
import logging
import inspect
import traceback
import functools
from itertools import groupby
from rez.config import config as rezconfig

from ..exceptions import SuiteReleaseError
from ..core import (
    SuiteOp,
    RollingContext,
    InstalledPackages,
    Storage,
    SuiteCtx,
    SavedSuite,
    PkgFamily,
    PkgVersion,
    re_resolve_rxt,
)
from ._vendor.Qt5 import QtCore, QtWidgets
from .widgets import BusyWidget, YesNoDialog, MessageDialog, ComboBox


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
                log.critical(
                    f"Thread {name!r} is busy, can't process {fn_name!r}."
                )
                return

            blocks_ = blocks or []
            busy_widgets = [
                w for w in BusyWidget.instances() if w.objectName() in blocks_
            ]  # type: list[BusyWidget]

            for widget in busy_widgets:
                widget.set_overwhelmed(name)

            def on_finished():
                for w in busy_widgets:
                    w.pop_overwhelmed(name)
                thread.finished.disconnect(on_finished)
                log.debug(f"Thread {name!r} finished {fn_name!r}.")

            thread.finished.connect(on_finished)

            log.debug(f"Thread {name!r} is about to run {fn_name!r}.")
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
    suite_viewed = QtCore.Signal(SavedSuite, str)
    suite_archived = QtCore.Signal(SavedSuite, bool)
    context_added = QtCore.Signal(SuiteCtx)
    context_stashed = QtCore.Signal(str, RollingContext)
    context_resolved = QtCore.Signal(str, RollingContext)
    context_dropped = QtCore.Signal(str)
    context_toggled = QtCore.Signal(str, int)
    context_renamed = QtCore.Signal(str, str)
    context_reordered = QtCore.Signal(list)
    request_edited = QtCore.Signal(str, bool)
    tools_updated = QtCore.Signal(list)
    pkg_scan_started = QtCore.Signal()
    pkg_families_scanned = QtCore.Signal(list)
    pkg_versions_scanned = QtCore.Signal(list)
    pkg_scan_ended = QtCore.Signal()
    storage_scan_started = QtCore.Signal()
    storage_scanned = QtCore.Signal(list)
    storage_scan_ended = QtCore.Signal()
    status_message = QtCore.Signal(str, int)

    def __init__(self):
        super(Controller, self).__init__(parent=None)

        # sending log messages to status-bar
        formatter = logging.Formatter(fmt="%(levelname)-8s %(message)s")
        handler = QtStatusBarHandler(self)
        handler.set_name("gui")
        handler.setFormatter(formatter)
        handler.setLevel(logging.INFO)
        log.addHandler(handler)

        self._sop = SuiteOp()
        self._sto = Storage()
        self._pkg = InstalledPackages()
        self._dirty = False
        self._edited = set()
        self._failed = set()
        self._disabled = dict()
        self._timers = dict()
        self._sender = dict()
        self._thread = dict()  # type: dict[str, Thread]

        self._resolve_param = {
            # exclude local packages by default
            "package_paths": rezconfig.nonlocal_packages_path,
        }

        _defer(on_time=500)(Controller.scan_suite_storage)(self)
        _defer(on_time=500)(Controller.scan_installed_packages)(self)
        _defer(on_time=600)(Controller.new_suite)(self)

    def sender(self):
        """Internal use. To preserve real signal sender for decorated method."""
        f = inspect.stack()[1].function
        return self._sender.pop(f, super(Controller, self).sender())

    @QtCore.Slot()  # noqa
    def on_suite_new_clicked(self):
        self._about_to_new(parent=self.sender())

    @QtCore.Slot(str, str, str)  # noqa
    @_defer(on_time=450)  # wait for requests-editor's edited signal
    def on_suite_save_clicked(self, name, desc, loaded_branch):
        self._about_to_save(name, desc, loaded_branch, parent=self.sender())

    @QtCore.Slot(str, str, bool)  # noqa
    def on_suite_load_clicked(self, name, branch, as_import):
        self._about_to_load(name, branch, as_import, parent=self.sender())

    @QtCore.Slot(SavedSuite)  # noqa
    @_defer(on_time=400)
    def on_saved_suite_selected(self, saved_suite):
        suite_branch = self.sender()
        if suite_branch.is_already_viewed(saved_suite):
            self.suite_viewed.emit(saved_suite, "")
        else:
            self.view_suite(saved_suite)
            suite_branch.mark_as_viewed(saved_suite)

    @QtCore.Slot(bool)  # noqa
    @_defer(on_time=100)
    def on_non_local_changed(self, state):
        self.set_non_local(state)

    @QtCore.Slot(str, bool)  # noqa
    def on_request_edited(self, name, edited):
        self._mark_request_edited(name, edited)

    @QtCore.Slot(str)  # noqa
    def on_stash_clicked(self, name):
        self.stash_context(name)

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

    @QtCore.Slot(str, int, list)  # noqa
    @_defer(on_time=50)
    def on_context_item_toggled(self, name, check_state, order):
        self.toggle_context(name, check_state, order)

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

    @QtCore.Slot(bool)  # noqa
    def on_suite_storage_scan_clicked(self, archived):
        self.scan_suite_storage(archived)

    @QtCore.Slot(list, bool)  # noqa
    def on_suites_archived(self, saved_suites, archive):
        self.set_suites_archived(saved_suites, archive)

    def _mark_request_edited(self, name, edited):
        if edited:
            self._edited.add(name)
        elif name in self._edited:
            self._edited.remove(name)
        self.request_edited.emit(name, edited)

    def stash_context(self, name):
        context = self._sop.get_context(name)
        self.context_stashed.emit(name, context)

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
        if name in self._edited:
            self._edited.remove(name)
            self._edited.add(new_name)
        if name in self._failed:
            self._failed.remove(name)
            self._failed.add(new_name)
        if name in self._disabled:
            self._disabled[new_name] = \
                self._disabled.pop(name)
        self.context_renamed.emit(name, new_name)
        self._tools_updated()

    @_thread(name="suiteOp", blocks=("SuitePage",))
    def drop_context(self, name):
        self._sop.drop_context(name)
        if name in self._edited:
            self._edited.remove(name)
        if name in self._failed:
            self._failed.remove(name)
        if name in self._disabled:
            self._disabled.pop(name)
        self.context_dropped.emit(name)
        self._tools_updated()

    @_thread(name="suiteOp", blocks=("SuitePage",))
    def reorder_contexts(self, new_order):
        enabled = [n for n in new_order if n not in self._disabled]
        self._sop.reorder_contexts(enabled)
        self.context_reordered.emit(new_order)
        self._tools_updated()

    @_thread(name="suiteOp", blocks=("SuitePage",))
    def toggle_context(self, name, check_state, order):
        if check_state:
            data = self._disabled.pop(name)
            self._sop.add_context(name, data["context"])
            self._sop.update_context(
                name, prefix=data["prefix"], suffix=data["suffix"],
            )
            for _name, alias in (data["tool_aliases"] or {}).items():
                self._sop.update_context(name, tool_name=name, new_alias=alias)
            for _name in data["hidden_tools"] or []:
                self._sop.update_context(name, tool_name=name, set_hidden=True)
            self._sop.reorder_contexts(order)
        else:
            self._disabled[name] = self._sop.get_context_data(name)
            self._sop.drop_context(name)

        self.context_toggled.emit(name, check_state)
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
    def set_non_local(self, exclude):
        package_paths = \
            rezconfig.nonlocal_packages_path if exclude \
            else rezconfig.packages_path

        self._resolve_param["package_paths"] = package_paths

        # update current suite
        #
        for ctx in self._sop.iter_contexts():
            context = re_resolve_rxt(ctx.context, package_paths=package_paths)
            self._context_resolved(ctx.name, context)

    @_thread(name="suiteOp", blocks=("SuitePage",))
    def resolve_context(self, name, requests):
        # todo: more args, and send a buffer in for verbose resolve logs.
        context = self._sop.resolve_context(
            requests,
            **self._resolve_param,
        )
        self._context_resolved(name, context)

    def _context_resolved(self, name, context):
        self.context_resolved.emit(name, context)
        if context.success:
            if name in self._failed:
                self._failed.remove(name)
            log.info(f"Context {name!r} resolved. See 'Context Info'.")
        else:
            self._failed.add(name)
            log.error(f"Context {name!r} resolve failed. See 'Context Info'.")
            # Replace failed context with an empty one for GUI to reflect the
            # fact that given requests is not valid. Thus tools from previous
            # resolved will be flushed.
            context = self._sop.resolve_context([])

        self._sop.update_context(name, context=context)
        self._tools_updated()

    def _tools_updated(self):
        self._dirty = True
        self.tools_updated.emit(list(self._sop.iter_tools()))

    @_thread(name="suiteOp", blocks=("SuitePage",))
    def new_suite(self):
        # note: there is a dirty check on widget side, checking unsaved change
        #   before asking controller to reset suite.
        self._reset_suite()
        # add a default context 'new'
        ctx = self._sop.add_context("new", self._sop.resolve_context([]))
        self.context_added.emit(ctx)

    @_thread(name="suiteOp", blocks=("SuitePage",))
    def save_suite(self, branch, name, description):
        # note: there is an edit check on widget side, checking edited and not
        #   yet resolved requests, before asking controller to save suite.
        path = self._sto.suite_path(branch, name)
        self._sop.set_description(description)

        try:
            self._sop.save(path)

        except SuiteReleaseError as e:
            message = f"{str(e)}\n" \
                      f"Check 'Exclude Local Packages' checkbox to fix this."
            log.error(message)
            self.suite_save_failed.emit(message)

        except Exception as e:
            message = f"\n{traceback.format_exc()}\n{str(e)}"
            log.error(message)
            self.suite_save_failed.emit(message)

        else:
            saved_suite = SavedSuite(
                name=name,
                branch=branch,
                path=path,
                archived=False,
                suite=None,  # lazy load
            )
            self._dirty = False
            self.suite_saved.emit(saved_suite)

    @_thread(name="suiteOp", blocks=("SuitePage", "StoragePage"))
    def load_suite(self, name, branch, as_import):
        self._reset_suite()
        path = self._sto.suite_path(branch, name)

        try:
            self._sop.load(path, as_import, re_resolve=False)
        except Exception as e:
            # widgets.SuiteInsightWidget already took cared of this with
            # traceback shown in tool view, simply prompt error message
            # here should be fine.
            message = f"Unable to load, suite corrupted: {path}"
            log.error(str(e))
            log.error(message)
            return

        # loaded
        description = self._sop.get_description()
        load_path = self._sop.loaded_from() or ""

        # stash saved contexts (.rxt)
        for ctx in self._sop.iter_contexts(ascending=True):
            self.context_added.emit(ctx)
            self.context_stashed.emit(ctx.name, ctx.context)

        # re-resolve contexts
        self._sop.re_resolve_rxt_contexts(**self._resolve_param)
        for ctx in self._sop.iter_contexts(ascending=True):
            self.context_resolved.emit(ctx.name, ctx.context)

        self._tools_updated()
        self._dirty = False
        self.suite_loaded.emit(name, description, load_path, branch)

    @_thread(name="suiteOp", blocks=("SuitePage", "StoragePage"))
    def view_suite(self, saved_suite):
        # read contexts into suite
        _ = list(saved_suite.iter_contexts())
        #   shouldn't raise any error while iterating contexts, because
        #   SweetSuite.contexts() already handled all exceptions with
        #   RollingContext yielded.

        try:
            # update tools into suite
            _ = list(saved_suite.iter_saved_tools())
        except Exception as e:
            log.warning("Error occurred in .rxt context (try re-resolve): "
                        f"{saved_suite.path}")
            error = f"{str(e)}\n\n{traceback.format_exc()}"
        else:
            error = ""

        self.suite_viewed.emit(saved_suite, error)

    @_thread(name="suiteOp", blocks=("SuitePage", "StoragePage"))
    def set_suites_archived(self, saved_suites, archive):
        """Mark a batch of saved suites as archived or not

        :param list[SavedSuite] saved_suites:
        :param bool archive: Archive state
        :return: None
        """
        for suite in saved_suites:
            changed = self._sto.set_archived(suite.path, archive=archive)
            if changed:
                self.suite_archived.emit(suite, archive)

    def _reset_suite(self):
        self._sop.reset()
        self._dirty = False
        self._edited = set()
        self._failed = set()
        self._disabled = dict()
        self.suite_newed.emit()

    def _about_to_new(self, parent):
        if not self._dirty:
            self.new_suite()
            return

        widget = QtWidgets.QLabel("Current changes not saved, discard ?")
        dialog = YesNoDialog(widget, yes_as_default=False, parent=parent)
        dialog.setWindowTitle("Unsaved Changes")

        def on_finished(result):
            if result:
                self.new_suite()

        dialog.finished.connect(on_finished)
        dialog.open()

    def _about_to_load(self, name, branch, as_import, parent):
        if not self._dirty:
            self.load_suite(name, branch, as_import)
            return

        widget = QtWidgets.QLabel("Current changes not saved, discard ?")
        dialog = YesNoDialog(widget, yes_as_default=False, parent=parent)
        dialog.setWindowTitle("Unsaved Changes")

        def on_finished(result):
            if result:
                self.load_suite(name, branch, as_import)

        dialog.finished.connect(on_finished)
        dialog.open()

    def _about_to_save(self, name, description, loaded_branch, parent):
        reason = self._objection_to_save_suite()
        if reason:
            dialog = MessageDialog(
                reason, "Cannot Save", level=logging.WARNING, parent=parent)
            dialog.open()
            return

        branches = self._sto.branches()
        if loaded_branch and loaded_branch not in branches:
            log.critical(f"Suite loaded from unknown branch {loaded_branch!r}.")
            # should not happen

        widget = QtWidgets.QWidget()
        _hint = QtWidgets.QLabel("Where to save suite ?")
        _box = ComboBox()
        _box.addItems(branches)
        if loaded_branch and loaded_branch in branches:
            _box.setCurrentText(loaded_branch)

        _layout = QtWidgets.QVBoxLayout(widget)
        _layout.addWidget(_hint)
        _layout.addWidget(_box)

        dialog = YesNoDialog(widget, parent=parent)
        dialog.setWindowTitle("Save Suite")

        def on_finished(result):
            if result:
                branch = _box.currentText()
                self.save_suite(branch, name, description)

        dialog.finished.connect(on_finished)
        dialog.open()

    def _objection_to_save_suite(self):
        if self._edited:
            reason = "Suite can't be saved, because:\n" \
                     "Context requests edited but not yet resolved:"
            for n in self._edited:
                reason += f"\n  - {n}"
            return reason

        elif self._failed:
            reason = "Suite can't be saved, because:\n" \
                     "Context requests failed to resolve:"
            for n in self._failed:
                reason += f"\n  - {n}"
            return reason

    @_thread(name="scanPkg")
    def scan_installed_packages(self):
        ct = QtCore.QThread.currentThread()
        log.info("Start scanning installed packages...")
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
        log.info(f"Found {_fm_count} families from {_path_count} locations.")
        log.info("Scanning versions...")
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
                f"locations {'.' * (int(i / 50) % 5)}", 5000
            )  # animated dots that also reflects the speed of the process.

        self.pkg_scan_ended.emit()
        log.info("All installed packages scanned.")

    @_thread(name="scanSuite", blocks=("StoragePage",))
    def scan_suite_storage(self, archived=False):
        ct = QtCore.QThread.currentThread()
        log.info("Start scanning saved suites...")
        self.storage_scan_started.emit()

        for branch in self._sto.branches():
            if ct.isInterruptionRequested():  # could be long running proc
                break
            self.storage_scanned.emit(
                list(self._sto.iter_saved_suites(branch, archived=archived)),
            )

        self.storage_scan_ended.emit()
        log.info("All saved suites scanned.")


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
        try:
            self._func(*self._args, **self._kwargs)
        except Exception as e:
            message = f"\n{traceback.format_exc()}\n{str(e)}"
            log.critical(message)


# https://docs.python.org/3/howto/logging-cookbook.html#a-qt-gui-for-logging
class QtStatusBarHandler(logging.Handler):
    def __init__(self, ctrl, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._ctrl = ctrl

    def emit(self, record):
        s = self.format(record)
        self._ctrl.status_message.emit(s, 5000)
