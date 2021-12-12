"""
Main business logic, with event notification
"""
import os
import uuid
from collections import namedtuple
from blinker import signal
from ._rezapi import SweetSuite
from rez.suite import Suite
from rez.resolved_context import ResolvedContext
from rez.exceptions import RezError, SuiteError


__all__ = (
    "SuiteOp",
    "Storage",

    "SuiteCtx",
    "SuiteTool",
    "SavedSuite",

    "SuiteOpError",
)


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


def _gen_ctx_id():
    return uuid.uuid4().hex


SuiteCtx = namedtuple(
    "SuiteCtx",
    ["name", "ctx_id", "context", "priority", "prefix", "suffix"]
)
SuiteTool = namedtuple(
    "SuiteTool",
    ["name", "alias", "hidden", "shadowed", "ctx_name", "ctx_id", "variant"]
)


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

        ctx_names = {
            _gen_ctx_id(): c["name"] for c in suite.contexts.keys()
        }
        # rename context name to ctx_id
        for ctx_id, name in ctx_names.items():
            suite.rename_context(name, ctx_id)

        self._suite = suite
        self._ctx_names = ctx_names

        self.sanity_check()
        self.refresh_tools()

    @classmethod
    def from_dict(cls, suite_dict):  # do we need this ?
        suite = SweetSuite.from_dict(suite_dict)
        return cls(suite)

    def to_dict(self):
        self.sanity_check()

        # swap ctx_id to name
        for ctx_id, name in self._ctx_names.items():
            self._suite.rename_context(ctx_id, name)

        suite_dict = self._suite.to_dict()

        # restore ctx_id
        for ctx_id, name in self._ctx_names.items():
            self._suite.rename_context(name, ctx_id)

        return suite_dict

    def sanity_check(self):
        for ctx_id in self._ctx_names.keys():
            if not self._suite.has_context(ctx_id):
                e = SuiteOpError("Context Id mismatch, invalid suite.")
                _emit_err(self, e, fatal=True)

        all_names = self._ctx_names.values()
        if len(all_names) != len(set(all_names)):
            e = SuiteOpError("Context name duplicated, invalid suite.")
            _emit_err(self, e, fatal=True)

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
        if name in self._ctx_names.values():
            e = "Duplicated name %r, no context added." % name
            _emit_err(self, SuiteOpError(e))
            return

        context = _resolved_ctx(requests)

        ctx_id = _gen_ctx_id()
        self._ctx_names[ctx_id] = name
        self._suite.add_context(name=ctx_id, context=context)

        data = self._suite.contexts[ctx_id]
        return self._ctx_data_to_tuple(data)

    def drop_context(self, ctx_id):
        """Remove context from suite"""
        self._ctx_names.pop(ctx_id, None)
        try:
            self._suite.remove_context(ctx_id)
        except SuiteError:
            pass  # no such context, should be okay to forgive

    def rename_context(self, ctx_id, new_name):
        if self._suite.has_context(ctx_id):
            if new_name not in self._ctx_names.values():
                self._ctx_names[ctx_id] = new_name
            else:
                e = "Duplicated name %r, no context renamed." % new_name
                _emit_err(self, SuiteOpError(e))
        else:
            e = "Context Id %r not exists, no context renamed." % ctx_id
            _emit_err(self, SuiteOpError(e))

    def lookup_context(self, ctx_id):
        return self._ctx_names.get(ctx_id)

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

    def update_context(self, ctx_id, requests=None, prefix=None, suffix=None):
        if requests is not None:
            self._suite.update_context(ctx_id, _resolved_ctx(requests))
        if prefix is not None:
            self._suite.set_context_prefix(ctx_id, prefix)
        if suffix is not None:
            self._suite.set_context_suffix(ctx_id, suffix)

    def lookup_tool(self, ctx_id, tool_alias):
        """Query tool's real name in specific context by alias

        Args:
            ctx_id (str): context Id
            tool_alias (str): tool alias

        Returns:
            str: tool name if found else None

        """
        self._suite.update_tools()

        def match(d):
            return d["context_name"] == ctx_id and d["tool_alias"] == tool_alias

        def find(entries):
            return next(filter(match, entries), None)

        in_shadowed = (find(x) for x in self._suite.tool_conflicts.values())
        matched = find(self._suite.tools.values()) \
            or find(self._suite.hidden_tools) \
            or next(filter(None, in_shadowed), None)

        return matched["tool_name"] if matched else None

    def update_tool(self, ctx_id, tool_name, new_alias=None, set_hidden=None):
        try:
            self._suite.validate_tool(ctx_id, tool_name)
        except SuiteError as e:
            _emit_err(self, e)
            return

        if new_alias is not None:
            self._suite.unalias_tool(ctx_id, tool_name)
            if new_alias:  # must unalias before set new alias or SuiteError
                self._suite.alias_tool(ctx_id, tool_name, new_alias)

        if set_hidden is not None:
            if set_hidden:
                self._suite.hide_tool(ctx_id, tool_name)
            else:
                self._suite.unhide_tool(ctx_id, tool_name)

    def refresh_tools(self):
        self._suite.refresh_tools()

    def iter_tools(self):
        self._suite.update_tools()

        for d in self._suite.tools.values():
            yield self._tool_data_to_tuple(d)

        for d in self._suite.hidden_tools:
            yield self._tool_data_to_tuple(d, hidden=True)

        for entries in self._suite.tool_conflicts.values():
            for d in entries:
                yield self._tool_data_to_tuple(d, shadowed=True)

    def _ctx_data_to_tuple(self, d, as_resolved=False):
        n = d["name"]
        c = self._suite.context(n) if as_resolved else d.get("context")
        return SuiteCtx(
            name=self.lookup_context(n),
            ctx_id=n,
            context=None if c is None else c.copy(),
            priority=d["priority"],
            prefix=d.get("prefix", ""),
            suffix=d.get("suffix", ""),
        )

    def _tool_data_to_tuple(self, d, hidden=False, shadowed=False):
        return SuiteTool(
            name=d["tool_name"],
            alias=d["tool_alias"],
            hidden=hidden,
            shadowed=shadowed,
            ctx_name=self.lookup_context(d["context_name"]),
            ctx_id=d["context_name"],
            variant=d["variant"],  # see TestCore.test_tool_by_multi_packages
        )


SavedSuite = namedtuple(
    "SavedSuite",
    ["name", "branch", "root", "bin", "filepath"]
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
