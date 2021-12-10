"""
Main business logic, with event notification
"""
import uuid
from collections import namedtuple
from blinker import signal
from ._rezapi import SweetSuite
from rez.suite import Suite
from rez.resolved_context import ResolvedContext
from rez.exceptions import RezError, SuiteError


__all__ = (
    "SuiteCtx",
    "SuiteOp",
    "Storage",
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
    ["name", "ctx_id", "context", "priority"]
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

        self._name = ""
        self._suite = suite
        self._ctx_names = ctx_names

        self.sanity_check()
        self.update_tools()

    @classmethod
    def from_dict(cls, suite_dict):
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
            e = SuiteOpError("Context count mismatch, invalid suite.")
            _emit_err(self, e, fatal=True)

        try:
            self._suite.validate()
        except SuiteError as e:
            _emit_err(self, e, fatal=True)

    def set_name(self, text):
        """Set suite name"""
        self._name = text

    def set_description(self, text):
        """Set suite description"""
        self._suite.set_description(text)

    def add_context(self, name, requests=None):
        """Add one resolved context to suite"""
        context = _resolved_ctx(requests)

        ctx_id = _gen_ctx_id()
        self._ctx_names[ctx_id] = name
        self._suite.add_context(name=ctx_id, context=context)

        return ctx_id

    def drop_context(self, ctx_id):
        """Remove context from suite"""
        self._ctx_names.pop(ctx_id, None)
        try:
            self._suite.remove_context(ctx_id)
        except SuiteError:
            pass  # no such context, should be okay to forgive

    def rename_context(self, ctx_id, new_name):
        if self._suite.has_context(ctx_id):
            self._ctx_names[ctx_id] = new_name
        else:
            e = SuiteOpError("Context Id %r not exists, no context renamed."
                             % ctx_id)
            _emit_err(self, e)

    def lookup_context(self, ctx_id):
        return self._ctx_names.get(ctx_id)

    def read_context(self, ctx_id, entry, default=None):
        return self._suite.read_context(ctx_id, entry, default)

    def find_contexts(self, in_request=None, in_resolve=None):
        """Find contexts in the suite based on search criteria."""
        return self._suite.find_contexts(in_request, in_resolve)

    def iter_contexts(self, sort_by_priority=True):
        ctx_data = self._suite.contexts.values()
        if sort_by_priority:
            ctx_data = sorted(ctx_data, key=lambda x: x["priority"])

        for data in ctx_data:
            yield SuiteCtx(
                name=self.lookup_context(data["name"]),
                ctx_id=data["name"],
                context=data["context"].copy(),
                priority=data["priority"],
            )

    def update_context(self, ctx_id, requests=None, prefix=None, suffix=None):
        if requests is not None:
            self._suite.update_context(ctx_id, _resolved_ctx(requests))
        if prefix is not None:
            self._suite.set_context_prefix(ctx_id, prefix)
        if suffix is not None:
            self._suite.set_context_suffix(ctx_id, suffix)

    def hide_tool(self):
        pass

    def alias_tool(self):
        pass

    def update_tools(self):
        self._suite.update_tools()


class Storage(object):
    """Suite storage"""
