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
    ["name", "context", "priority", "prefix", "suffix", "loaded", "from_rxt"]
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

    def add_context(self, name, context):
        """Add one resolved context to suite

        The context `name` must not exists in suite nor an empty string. And
        the `context` object must be a success resolved one.

        If inputs not able to meet the condition above, nothing will change
        and returns `None` with `SuiteOpWarning` issued (or error raised if
        warnings are being treated as error).

        :param str name: Name to store the context under.
        :param ResolvedContext context: A resolved-context to add.
        :return: `None` if failed, or a `SuiteCtx` that represents the context
            just being added.
        :rtype: None or SuiteCtx
        """
        if self._suite.has_context(name):
            _warn("Context already in suite: %r" % name)
            return

        if not context.success:
            _warn("Context is not resolved: %r" % name)
            return

        try:
            self._suite.add_context(name=name, context=context)
        except SuiteError as e:
            _warn(str(e), category=ContextNameWarning)
            return

        data = self._suite.contexts[name]
        return self._ctx_data_to_tuple(data)

    def drop_context(self, name):
        """Remove context from suite"""
        try:
            self._suite.remove_context(name)
        except SuiteError:
            pass  # no such context, should be okay to forgive

    def update_context(
            self,
            name,
            new_name=None,
            context=None,
            prefix=None,
            suffix=None,
            tool_name=None,
            new_alias=None,
            set_hidden=None,
    ):
        """Update one context in suite

        The context `name` must exists in suite, and the `context` object,
        if given, must be a success resolved one.

        New context name `new_name` cannot be an empty string, and must not
        already exists in suite.

        When updating tool with `new_alias` or `set_hidden`, `tool_name` must
        given. If tool and `context` both are being updated, `tool_name` must
        exists in the given `context` object.

        If inputs not able to meet all conditions above, nothing will update
        and returns `None` with `SuiteOpWarning` issued (or error raised if
        warnings are being treated as error).

        If update success, a `SuiteCtx` and a `SuiteTool` (if a tool updated
        or `None`) instance will be return in a tuple as an update record.

        :param str name: The name of existing suite context.
        :param new_name: Rename context.
        :param context: Replace resolved-context.
        :param prefix: Change context prefix.
        :param suffix: Change context suffix.
        :param tool_name: The name of the tool in context `name`.
        :param new_alias: Change tool alias, `tool_name` must be given.
        :param set_hidden: Change tool visibility, `tool_name` must be given.
        :type new_name: str or None
        :type context: ResolvedContext or None
        :type prefix: str or None
        :type suffix: str or None
        :type tool_name: str or None
        :type new_alias: str or None
        :type set_hidden: bool or None
        :return: None if invalid inputs, or, a suite context representation
            and a tool representation (if tool updated) in a tuple.
        :rtype: None or tuple[SuiteCtx, None] or tuple[SuiteCtx, SuiteTool]
        """
        ctx_name = name

        if not self._suite.has_context(ctx_name):
            _warn("No such context in suite: %r" % ctx_name)
            return

        if context and not context.success:
            _warn("Context is not resolved: %r" % ctx_name)
            return

        updating_tool = new_alias is not None or set_hidden is not None
        if updating_tool:
            if not tool_name:
                _warn("Arg `tool_name` must be given for updating tool.")
                return

            _ctx = context or self._suite.context(ctx_name)
            if not self._ctx_tool_exists(_ctx, tool_name):
                _warn("No such tool %r in context %r" % (tool_name, ctx_name))
                return

        # updating context

        if new_name is not None:
            try:
                self._suite.rename_context(ctx_name, new_name)
            except SuiteError as e:
                _warn(str(e), category=ContextNameWarning)
                return
            else:
                ctx_name = new_name

        if context is not None:
            self._suite.update_context(ctx_name, context)
        if prefix is not None:
            self._suite.set_context_prefix(ctx_name, prefix)
        if suffix is not None:
            self._suite.set_context_suffix(ctx_name, suffix)

        # updating tool

        if tool_name and new_alias is not None:
            self._suite.unalias_tool(ctx_name, tool_name)
            if new_alias:  # must unalias before set new alias or SuiteError
                self._suite.alias_tool(ctx_name, tool_name, new_alias)

        if tool_name and set_hidden is not None:
            if set_hidden:
                self._suite.hide_tool(ctx_name, tool_name)
            else:
                self._suite.unhide_tool(ctx_name, tool_name)

        # results

        updated_ctx = self._ctx_data_to_tuple(self._suite.contexts[ctx_name])
        updated_tool = next((
            t for t in self.iter_tools(context_name=ctx_name)
            if t.name == tool_name
        ), None)

        return updated_ctx, updated_tool

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

    def iter_tools(self, context_name=None):
        self._suite.update_tools()
        seen = set()

        def _match_context(d_):
            return context_name is None or context_name == d_["context_name"]

        invalid = Constants.st_valid
        for d in self._suite.tools.values():
            seen.add(d["tool_alias"])
            if _match_context(d):
                yield self._tool_data_to_tuple(d, invalid=invalid)

        invalid = Constants.st_hidden
        for d in self._suite.hidden_tools:
            seen.add(d["tool_alias"])
            if _match_context(d):
                yield self._tool_data_to_tuple(d, invalid=invalid)

        invalid = Constants.st_shadowed
        for entries in self._suite.tool_conflicts.values():
            for d in entries:
                seen.add(d["tool_alias"])
                if _match_context(d):
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
                    if _match_context(d):
                        yield self._tool_data_to_tuple(d, invalid=invalid)

    def _ctx_tool_exists(self, context, tool_name):
        context_tools = context.get_tools(request_only=True)
        for _, tool_names in context_tools.values():
            if tool_name in tool_names:
                return True
        return False

    def _ctx_data_to_tuple(self, d, as_resolved=False):
        n = d["name"]
        c = self._suite.context(n) if as_resolved else d.get("context")
        return SuiteCtx(
            name=n,
            context=c.copy() if c else None,
            priority=d["priority"],
            prefix=d.get("prefix", ""),
            suffix=d.get("suffix", ""),
            loaded=d.get("loaded"),
            from_rxt=c.load_path if c else None,
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
