"""
Main business logic, with event notification
"""
import os
import warnings
from collections import namedtuple
from rez.vendor import yaml
from rez.config import config as rezconfig
from rez.utils.formatting import PackageRequest
from rez.resolved_context import ResolvedContext
from rez.resolver import ResolverStatus
from . import signals, util
from ._rezapi import SweetSuite
from .constants import (
    TOOL_VALID,
    TOOL_HIDDEN,
    TOOL_SHADOWED,
    TOOL_MISSING,
)
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
    ["name", "alias", "status", "ctx_name", "variant"]
)
SavedSuite = namedtuple(
    "SavedSuite",
    ["name", "branch", "path"]
)


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
            s = SweetSuite()

            # Attach signal senders
            s.flush_tools = s._flush_tools = util.attach_sender(
                sender=self, func=s.flush_tools, signal=signals.tool_flushed)
            s.update_tools = s._update_tools = util.attach_sender(
                sender=self, func=s.update_tools, signal=signals.tool_updated)

            self._working_suite = s
        return self._working_suite

    def reset(self):
        self._working_suite = None

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
        """Returns location where suite previously saved at

        :return: Suite's load_path, if any.
        :rtype: str or None
        """
        return self._suite.load_path

    def refresh(self):
        """Flush and update all tools in suite

        :return: None
        """
        self._suite.flush_tools()
        self._suite.update_tools()

    def sanity_check(self):
        """Ensure suite is valid.

        :return: None
        :raise SuiteOpError: If suite validation failed.
        """
        try:
            self._suite.validate()
        except SuiteError as e:
            raise SuiteOpError(e)

    def set_description(self, text):
        """Set suite description

        :param str text: The description (comment) string for the suite.
        :return: None
        """
        self._suite.set_description(text)

    def set_load_path(self, path):
        """Explicitly set suite's load_path

        :param str path: The location where suite saved at.
        :return: None
        """
        self._suite.load_path = path

    def add_context(self, name, requests):
        """Add one resolved context to suite

        The context `name` must not exists in suite nor an empty string. And
        the `context` object must be a success resolved one.

        If inputs not able to meet the condition above, nothing will change
        and returns `None` with `SuiteOpWarning` issued (or error raised if
        warnings are being treated as error).

        :param str name: Name to store the context under.
        :param requests: List of strings or PackageRequest objects representing
            the request for resolving a context to add.
        :type requests: list[str or PackageRequest]
        :return: None if failed, or a SuiteCtx that represents the context
            just being added.
        :rtype: None or SuiteCtx
        """
        if self._suite.has_context(name):
            _warn("Context already in suite: %r" % name)
            return

        context = self._resolve_context(requests)

        if not context.success:
            _d = context.failure_description
            _m = "Context %r not resolved: %s" % (name, _d)
            _warn(_m, category=ContextBrokenWarning)
            return

        try:
            self._suite.add_context(name=name, context=context)
        except SuiteError as e:
            _warn(str(e), category=ContextNameWarning)
            return

        data = self._suite.contexts[name]
        return self._ctx_data_to_tuple(data)

    def drop_context(self, name):
        """Remove context from suite

        Dropping context that is not exists in suite will be forgiven (no
        error raised).

        :param name: The name of context to remove.
        :return: None
        :rtype: None
        """
        try:
            self._suite.remove_context(name)
        except SuiteError:
            pass  # no such context, should be okay to forgive

    def reorder_contexts(self, new_order):
        """Reorder contexts in new priority

        The `new_order` must contains the name of all contexts in suite.

        Preceding context name in the `new_order` list will have a higher
        priority than the latter ones.

        :param new_order: A list of all context names to represent new order.
        :type new_order: list
        :return: None
        :rtype: None
        :raises SuiteOpError: If `new_order` not matching all context names
            in suite.
        """
        if set(new_order) != set(self._suite.contexts.keys()):
            raise SuiteOpError("Input context names not matching current "
                               "suites.")

        new_priority = 0
        for new_priority, name in enumerate(reversed(new_order)):
            data = self._suite.contexts[name]
            data["priority"] = new_priority

        self._suite.next_priority = new_priority + 1
        self._suite.flush_tools()

    def update_context(
            self,
            name,
            new_name=None,
            requests=None,
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

        If update success, a `SuiteCtx` instance will be returned as update
        record.

        :param str name: The name of existing suite context.
        :param new_name: Rename context.
        :param requests: List of strings or PackageRequest objects representing
            the request for resolving a context to replace one if given.
        :param prefix: Change context prefix.
        :param suffix: Change context suffix.
        :param tool_name: The name of the tool in context `name`.
        :param new_alias: Change tool alias, `tool_name` must be given.
        :param set_hidden: Change tool visibility, `tool_name` must be given.
        :type new_name: str or None
        :type requests: list[str or PackageRequest] or None
        :type prefix: str or None
        :type suffix: str or None
        :type tool_name: str or None
        :type new_alias: str or None
        :type set_hidden: bool or None
        :return: None if invalid inputs, or, a suite context representation.
        :rtype: None or SuiteCtx
        """
        ctx_name = name

        if not self._suite.has_context(ctx_name):
            _warn("No such context in suite: %r" % ctx_name)
            return

        context = None if requests is None else self._resolve_context(requests)

        if context is not None and not context.success:
            _d = context.failure_description
            _m = "Context %r not resolved: %s" % (name, _d)
            _warn(_m, category=ContextBrokenWarning)
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
        signals.ctx_updating.send(self)

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

        signals.ctx_updated.send(self)

        # results

        data = self._suite.contexts[ctx_name]
        return self._ctx_data_to_tuple(data)

    def find_contexts(self, in_request=None, in_resolve=None):
        """Find contexts in the suite based on search criteria

        :param in_request: Match contexts that contain the given package in
            their request.
        :param in_resolve: Match contexts that contain the given package in
            their resolve. You can also supply a conflict requirement '!foo'
            which will match any contexts whose resolve does not contain any
            version of package 'foo'.
        :type in_request: str or None
        :type in_resolve: str or PackageRequest or None
        :return: List of context names that match the search criteria.
        :rtype: list[str]
        """
        return self._suite.find_contexts(in_request, in_resolve)

    def iter_contexts(self, as_resolved=False, ascending=False):
        """Iterate contexts in suite in priority ordered

        By default (descending ordered), the context that has higher priority
        will be iterated first.

        :param as_resolved: Ensure context resolved if True.
        :param ascending: Iter contexts by priority in ascending order.
        :type as_resolved: bool or False
        :type ascending: bool or False
        :return: An SuiteCtx object iterator
        :rtype: collections.Iterator[SuiteCtx]
        """
        ctx_data = sorted(
            self._suite.contexts.values(), key=lambda x: x["priority"],
            reverse=not ascending
        )
        for d in ctx_data:
            yield self._ctx_data_to_tuple(d, as_resolved=as_resolved)

    def iter_tools(self, context_name=None):
        """Iterate all tools in suite

        Suite tools will be iterated in following order:
            - Valid, not being hidden, not in conflict
            - Hidden
            - Shadowed (name/alias conflicts with other tool)
            - Missing (due to failed context resolved)

        A previously saved suite may have missing tools due to the request
        of the context is no longer resolvable in current condition.

        :param context_name: Only yield tools in this context.
        :type context_name: str or None
        :return: An SuiteTool object iterator
        :rtype: collections.Iterator[SuiteTool]
        """
        self._suite.update_tools()
        seen = set()

        def _match_context(d_):
            return context_name is None or context_name == d_["context_name"]

        status = TOOL_VALID
        for d in self._suite.tools.values():
            seen.add(d["tool_alias"])
            if _match_context(d):
                yield self._tool_data_to_tuple(d, status=status)

        status = TOOL_HIDDEN
        for d in self._suite.hidden_tools:
            seen.add(d["tool_alias"])
            if _match_context(d):
                yield self._tool_data_to_tuple(d, status=status)

        status = TOOL_SHADOWED
        for entries in self._suite.tool_conflicts.values():
            for d in entries:
                seen.add(d["tool_alias"])
                if _match_context(d):
                    yield self._tool_data_to_tuple(d, status=status)

        status = TOOL_MISSING
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
                        yield self._tool_data_to_tuple(d, status=status)

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

    def _tool_data_to_tuple(self, d, status=0):
        return SuiteTool(
            name=d["tool_name"],
            alias=d["tool_alias"],
            status=status,
            ctx_name=d["context_name"],
            variant=d["variant"],  # see TestCore.test_tool_by_multi_packages
        )

    def _resolve_context(self, requests):
        """Try resolving a context

        :param requests: List of strings or PackageRequest objects representing
            the request for resolving a context.
        :type requests: list[str or PackageRequest]
        :return: A ResolvedContext object if succeed or BrokenContext if not.
        :rtype: ResolvedContext or BrokenContext
        """
        try:
            context = ResolvedContext(requests)
        except RezError as e:
            context = BrokenContext(str(e))

        signals.ctx_resolved.send(self, success=context.success)

        return context


class BrokenContext(object):
    """A simple representation of a failed context"""
    def __init__(self, failure_description):
        self.failure_description = failure_description

    @property
    def success(self):
        return False

    @property
    def status(self):
        return ResolverStatus.failed


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
