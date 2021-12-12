"""
Main business logic, with event notification
"""
import os
import uuid
from collections import namedtuple
from blinker import signal
from ._rezapi import SweetSuite
from rez.suite import Suite
from rez.config import config as rezconfig
from rez.resolved_context import ResolvedContext
from rez.exceptions import RezError, SuiteError


sweetconfig = rezconfig.plugins.command.sweet


# TODO:
#     * live/bake per context
#     * use signal to set suite dirty ?
#     * do we need SuiteOp.from_dict() ?
#     * do we need foolproof SweetSuite.from_dict() ?


__all__ = (
    "SuiteOp",
    "Storage",
    "Constants",

    "SuiteCtx",
    "SuiteTool",
    "SavedSuite",

    "SuiteOpError",
)


SuiteCtx = namedtuple(
    "SuiteCtx",
    ["name", "context", "priority", "prefix", "suffix"]
)
SuiteTool = namedtuple(
    "SuiteTool",
    ["name", "alias", "invalid", "ctx_name", "variant"]
)
SavedSuite = namedtuple(
    "SavedSuite",
    ["name", "branch", "root", "bin", "filepath"]
)
OpenedSuite = namedtuple(
    "OpenedSuite",
    []
)


class Constants(object):
    # suite tool (st) status code
    st_valid = 0
    st_hidden = 1
    st_shadowed = 2
    st_missing = -1


class Session(object):

    def __init__(self):
        self._storages = [
            (branch, Storage(root, branch))
            for branch, root in sweetconfig.suite_roots().items()
        ]
        self._suites = dict()

    def iter_saved_suites(self, branch=None):
        # type: (str) -> [SavedSuite]
        for b, storage in self._storages:
            if branch and b != branch:
                continue
            for saved_suite in storage.iter_saved_suites():
                yield saved_suite

    def load(self, saved_suite):
        pass

    def save(self, name):
        pass  # return SavedSuite

    def new(self):
        self._suites["*"] = SuiteOp()
        # connect signals


class SuiteOpError(SuiteError):
    """Suite operation error"""


def _emit_err(sender, err, fatal=False):
    sig_err = signal("sweet:error")
    if bool(sig_err.receivers):
        sig_err.send(sender, err=err)
        if fatal:
            raise err
    else:
        raise err


def _resolved_ctx(requests):
    """"""
    try:
        context = ResolvedContext(requests)
    except (RezError, Exception) as e:
        context = ResolvedContext([])
        _emit_err("ResolvedContext", e)

    # todo: emit context resolved
    return context


def _unique_id():
    return uuid.uuid4().hex


class SuiteOp(object):
    """Suite operator"""

    def __init__(self, suite=None):
        suite = suite or SweetSuite()

        if not isinstance(suite, Suite):
            t = type(suite)
            e = SuiteOpError("Expecting 'Suite' or 'SweetSuite', got %r." % t)
            _emit_err(self, e)

            suite = SweetSuite()

        if not isinstance(suite, SweetSuite):
            suite = SweetSuite.from_dict(suite.to_dict())

        self._suite = suite

        self.sanity_check()
        self.refresh_tools()

    @classmethod
    def from_dict(cls, suite_dict):  # do we need this ?
        suite = SweetSuite.from_dict(suite_dict)
        return cls(suite)

    def to_dict(self):
        self.sanity_check()
        suite_dict = self._suite.to_dict()
        return suite_dict

    def sanity_check(self):
        try:
            self._suite.validate()
        except SuiteError as e:
            _emit_err(self, e, fatal=True)

    def set_description(self, text):
        """Set suite description"""
        self._suite.set_description(text)

    def set_load_path(self, path):
        self._suite.load_path = path

    def add_context(self, name, requests=None):
        """Add one resolved context to suite"""
        if self._suite.has_context(name):
            e = "Duplicated name %r, no context added." % name
            _emit_err(self, SuiteOpError(e))
            return

        context = _resolved_ctx(requests or [])
        self._suite.add_context(name=name, context=context)

        data = self._suite.contexts[name]
        return self._ctx_data_to_tuple(data)

    def drop_context(self, name):
        """Remove context from suite"""
        try:
            self._suite.remove_context(name)
        except SuiteError:
            pass  # no such context, should be okay to forgive

    def rename_context(self, old_name, new_name):
        if self._suite.has_context(old_name):
            if not self._suite.has_context(new_name):
                self._suite.rename_context(old_name, new_name)
            else:
                e = "Duplicated name %r, no context renamed." % new_name
                _emit_err(self, SuiteOpError(e))
        else:
            e = "Context %r not exists, no context renamed." % old_name
            _emit_err(self, SuiteOpError(e))

    def find_contexts(self, in_request=None, in_resolve=None):
        """Find contexts in the suite based on search criteria."""
        return self._suite.find_contexts(in_request, in_resolve)

    def iter_contexts(self, as_resolved=False, ascending=False):
        ctx_data = sorted(
            self._suite.contexts.values(), key=lambda x: x["priority"],
            reverse=not ascending
        )
        for d in ctx_data:
            yield self._ctx_data_to_tuple(d, as_resolved=as_resolved)

    def update_context(self, name, requests=None, prefix=None, suffix=None):
        if requests is not None:
            self._suite.update_context(name, _resolved_ctx(requests))
        if prefix is not None:
            self._suite.set_context_prefix(name, prefix)
        if suffix is not None:
            self._suite.set_context_suffix(name, suffix)

    def update_tool(self, ctx_name, tool_name, new_alias=None, set_hidden=None):
        try:
            self._suite.validate_tool(ctx_name, tool_name)
        except SuiteError as e:
            _emit_err(self, e)
            return

        if new_alias is not None:
            self._suite.unalias_tool(ctx_name, tool_name)
            if new_alias:  # must unalias before set new alias or SuiteError
                self._suite.alias_tool(ctx_name, tool_name, new_alias)

        if set_hidden is not None:
            if set_hidden:
                self._suite.hide_tool(ctx_name, tool_name)
            else:
                self._suite.unhide_tool(ctx_name, tool_name)

    def refresh_tools(self):
        self._suite.refresh_tools()

    def iter_tools(self):
        self._suite.update_tools()
        seen = set()

        invalid = Constants.st_valid
        for d in self._suite.tools.values():
            seen.add(d["tool_alias"])
            yield self._tool_data_to_tuple(d, invalid=invalid)

        invalid = Constants.st_hidden
        for d in self._suite.hidden_tools:
            seen.add(d["tool_alias"])
            yield self._tool_data_to_tuple(d, invalid=invalid)

        invalid = Constants.st_shadowed
        for entries in self._suite.tool_conflicts.values():
            for d in entries:
                seen.add(d["tool_alias"])
                yield self._tool_data_to_tuple(d, invalid=invalid)

        invalid = Constants.st_missing
        for ctx_name, cached_d in self._suite.saved_tools.items():
            for t_alias, t_name in cached_d.items():
                if t_alias not in seen:
                    d = {
                        "tool_name": t_name,
                        "tool_alias": t_alias,
                        "context_name": ctx_name,
                        "variant": None,
                    }
                    yield self._tool_data_to_tuple(d, invalid=invalid)

    def _ctx_data_to_tuple(self, d, as_resolved=False):
        n = d["name"]
        c = self._suite.context(n) if as_resolved else d.get("context")
        return SuiteCtx(
            name=n,
            context=None if c is None else c.copy(),
            priority=d["priority"],
            prefix=d.get("prefix", ""),
            suffix=d.get("suffix", ""),
        )

    def _tool_data_to_tuple(self, d, invalid=0):
        return SuiteTool(
            name=d["tool_name"],
            alias=d["tool_alias"],
            invalid=invalid,
            ctx_name=d["context_name"],
            variant=d["variant"],  # see TestCore.test_tool_by_multi_packages
        )


class Storage(object):
    """Suite storage"""

    def __init__(self, root, branch=None):
        self._root = root
        self._branch = branch or os.path.basename(root)

    @property
    def root(self):
        return self._root

    @property
    def branch(self):
        return self._branch

    def _suite_dir(self, name):
        return os.path.join(self._root, name)

    def _suite_bin(self, name):
        return os.path.join(self._suite_dir(name), "bin")

    def _suite_file(self, name):
        return os.path.join(self._suite_dir(name), "suite.yaml")

    def load(self, filepath):
        return SweetSuite.load(filepath)

    def save(self, suite_dict, name, callback=None):
        suite_dir = self._suite_dir(name)
        suite = SweetSuite.from_dict(suite_dict)
        suite.save(suite_dir)

        if callback is not None:
            callback(suite, suite_dir)

        return self._suite_file(name)

    def iter_saved_suites(self):
        if not os.path.isdir(self._root):
            return

        for name in os.listdir(self._root):
            filepath = self._suite_file(name)
            if os.path.isfile(filepath):
                yield SavedSuite(
                    name=name,
                    branch=self._branch,
                    root=self._root,
                    bin=self._suite_bin(name),
                    filepath=filepath,
                )
