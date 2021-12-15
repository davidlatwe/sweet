"""
Main business logic, with event notification
"""
import os
import copy
import warnings
from collections import namedtuple
from blinker import signal
from rez.suite import Suite
from rez.vendor import yaml
from rez.config import config as rezconfig
from rez.resolved_context import ResolvedContext
from ._rezapi import SweetSuite
from .exceptions import (
    RezError,
    SuiteError,
    SuiteOpError,
    SuiteIOError,
    SuiteOpWarning,
    ContextNameWarning,
    ContextBrokenWarning,
)


sweetconfig = rezconfig.plugins.command.sweet


# TODO:
#     * use signal to set suite dirty ?


__all__ = (
    "SuiteOp",
    "Storage",
    "Constants",

    "SuiteCtx",
    "SuiteTool",
    "SavedSuite",
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
    ["name", "branch", "path"]
)


class Constants(object):
    # suite tool (st) status code
    st_valid = 0
    st_hidden = 1
    st_shadowed = 2
    st_missing = -1


class Session(object):

    def __init__(self):
        self._suites = dict()

    def load(self, saved_suite):
        pass

    def save(self, name):
        pass  # return SavedSuite

    def new(self):
        self._suites["*"] = SuiteOp()
        # connect signals


def _emit_err(sender, err, fatal=False):
    sig_err = signal("sweet:error")
    if bool(sig_err.receivers):
        sig_err.send(sender, err=err)
        if fatal:
            raise err
    else:
        raise err


def _warn(message, category=None):
    category = category or SuiteOpWarning
    warnings.warn(message, category=category, stacklevel=2)


class SuiteOp(object):
    """Suite operator"""

    def __init__(self):
        self._working_suite = None

    @property
    def _suite(self):
        if self._working_suite is None:
            self._working_suite = SweetSuite()
        return self._working_suite

    def dump(self):
        suite_dict = self._suite.to_dict()

        for name, data in self._suite.contexts.items():
            context = data.get("context")
            if context:
                suite_dict["contexts"][name]["context"] = context.copy()
            loaded = data.get("loaded")
            if loaded:
                suite_dict["contexts"][name]["loaded"] = True

        return suite_dict

    def load(self, path):
        # type: (str) -> None

        filepath = os.path.join(path, "suite.yaml")
        if not os.path.exists(filepath):
            raise SuiteIOError("Not a suite: %r" % path)

        try:
            with open(filepath, "rb") as f:
                suite_dict = yaml.load(f, Loader=yaml.FullLoader)  # noqa
        except yaml.YAMLError as e:  # noqa
            raise SuiteIOError("Failed loading suite: %s" % str(e))

        suite = SweetSuite.from_dict(suite_dict)
        suite.load_path = os.path.realpath(path)

        self._working_suite = suite

    def save(self, path):
        # type: (str) -> None

        self.sanity_check()
        # note: cannot save over if load_path is None
        self._suite.save(path)

    def loaded_from(self):
        return self._suite.load_path

    def refresh(self):
        self._suite.refresh_tools()

    def sanity_check(self):
        try:
            self._suite.validate()
        except SuiteError as e:
            raise SuiteOpError(e)

    def set_description(self, text):
        """Set suite description"""
        self._suite.set_description(text)

    def set_load_path(self, path):
        self._suite.load_path = path

    def add_context(self, name, requests=None):
        """Add one resolved context to suite"""
        if self._suite.has_context(name):
            _warn("Duplicated name %r, no context added." % name,
                  category=ContextNameWarning)
            return

        context = self._resolved_ctx(requests or [])
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
                _warn("Duplicated name %r, no context renamed." % new_name,
                      category=ContextNameWarning)
        else:
            _warn("Context %r not exists, no context renamed." % old_name,
                  category=SuiteOpWarning)

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
            self._suite.update_context(name, self._resolved_ctx(requests))
        if prefix is not None:
            self._suite.set_context_prefix(name, prefix)
        if suffix is not None:
            self._suite.set_context_suffix(name, suffix)

    def update_tool(self, ctx_name, tool_name, new_alias=None, set_hidden=None):
        try:
            self._suite.validate_tool(ctx_name, tool_name)
        except SuiteError as e:
            _warn(str(e), category=SuiteOpWarning)
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
            context=c.copy() if c else None,
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

    def _resolved_ctx(self, requests):
        """"""
        try:
            context = ResolvedContext(requests)
        except (RezError, Exception) as e:
            context = ResolvedContext([])
            _warn(str(e), category=ContextBrokenWarning)

        # todo: emit context resolved
        return context


class Storage(object):
    """Suite storage"""

    def __init__(self, roots):
        roots = roots or sweetconfig.suite_roots()  # type: dict
        assert isinstance(roots, dict)
        self._roots = roots

    def __repr__(self):
        return "%s(%s)" % (
            self.__class__.__name__,
            ", ".join("%s=%s" % (b, path) for b, path in self._roots)
        )

    def suite_path(self, branch, name):
        # type: (str, str) -> str

        try:
            root = self._roots[branch]
        except KeyError:
            raise SuiteIOError("Unknown storage branch: %r" % branch)

        return os.path.join(root, name)

    def iter_saved_suites(self, branch=None):
        # type: (str) -> [SavedSuite]

        for b, root in self._roots.items():
            if branch and b != branch:
                continue

            if not os.path.isdir(root):
                continue

            for name in os.listdir(root):
                path = os.path.join(root, name)
                filepath = os.path.join(path, "suite.yaml")

                if os.path.isfile(filepath):
                    yield SavedSuite(
                        name=name,
                        branch=b,
                        path=path,
                    )
