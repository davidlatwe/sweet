"""
Main business logic, with event notification
"""
import os
import sys
import logging
import warnings
from typing import List
from dataclasses import dataclass
from contextlib import contextmanager
from collections import MutableMapping

from rez.vendor import yaml
from rez.suite import Suite
from rez.config import config as rezconfig
from rez.utils.yaml import dump_yaml
from rez.utils.filesystem import forceful_rmtree
from rez.utils.execution import create_forwarding_script
from rez.utils.formatting import PackageRequest
from rez.resolver import ResolverStatus
from rez.vendor.version.version import Version
from rez.resolved_context import ResolvedContext
from rez.packages import iter_package_families, iter_packages, Variant
from rez.package_repository import package_repository_manager

from . import util
from .exceptions import (
    ResolvedContextError,
    SuiteError,
    SuiteOpError,
    SuiteIOError,
    SuiteOpWarning,
    ContextNameWarning,
    ContextBrokenWarning,
)

log = logging.getLogger("sweet")


sweetconfig = rezconfig.plugins.command.sweet
# todo: load rezconfig from suite-saving path


__all__ = (
    "SuiteOp",
    "Storage",
    "InstalledPackages",

    "SuiteCtx",
    "SuiteTool",
    "SavedSuite",
    "PkgFamily",
    "PkgVersion",
    "BrokenContext",

    "Constants",
)


class Constants:
    # suite tool status code
    #
    TOOL_VALID = 0
    TOOL_HIDDEN = 1
    TOOL_SHADOWED = 2
    TOOL_MISSING = -1


@dataclass
class SuiteCtx:
    __slots__ = "name", "priority", "prefix", "suffix", \
                "context", "requests", "resolves"
    name: str
    priority: int
    prefix: str
    suffix: str
    context: "RollingContext"
    requests: List[PackageRequest]
    resolves: List[Variant]
    # Advance options
    # timestamp
    # package_paths
    # package_filter
    # package_orderers
    # building


@dataclass
class SuiteTool:
    __slots__ = "name", "alias", "status", "ctx_name", "variant", \
                "location", "uri"
    name: str
    alias: str
    status: int
    ctx_name: str
    variant: Variant
    location: str
    uri: str


@dataclass
class PkgFamily:
    __slots__ = "name", "location"
    name: str
    location: str


@dataclass
class PkgVersion:
    __slots__ = "name", "version", "qualified", "requires", "variants", \
                "tools", "uri", "timestamp", "location", "is_nonlocal"
    name: str
    version: Version
    qualified: str
    requires: List[str]
    variants: List[List[str]]
    tools: List[str]
    uri: str
    timestamp: int
    location: str
    is_nonlocal: bool


@dataclass
class SavedSuite:
    __slots__ = "name", "branch", "path", "archived", "suite"
    name: str
    branch: str
    path: str
    archived: bool
    suite: "SweetSuite" or None

    @property
    def _suite(self):
        if self.suite is None:
            self.suite = SweetSuite.load(self.path)  # context not yet loaded
        return self.suite

    @property
    def is_live(self):
        return self._suite.is_live()

    @property
    def description(self):
        return self._suite.description

    def iter_saved_tools(self):
        """
        :return: A SuiteTool object iterator
        :rtype: collections.Iterator[SuiteTool]
        """
        sop = SuiteOp()
        sop._working_suite = self._suite
        return sop.iter_tools(visible_only=True)

    def iter_contexts(self, ascending=False):
        """Iterate contexts (from rxt files) in suite in priority ordered

        By default (descending ordered), the context that has higher priority
        will be iterated first.

        :param ascending: Iter contexts by priority in ascending order.
        :type ascending: bool or False
        :return: An context name, resolved-context tuple pair iterator
        :rtype: collections.Iterator[SuiteCtx]
        """
        sop = SuiteOp()
        sop._working_suite = self._suite
        return sop.iter_contexts(ascending=ascending)


def _warn(message, category=None):
    category = category or SuiteOpWarning
    warnings.warn(message, category=category, stacklevel=2)


class SuiteOp(object):
    """Suite operator"""

    def __init__(self):
        self._working_suite = None   # type: SweetSuite or None
        self._previous_tools = None  # type: list[SuiteTool] or None

    @property
    def _suite(self):
        if self._working_suite is None:
            s = SweetSuite()
            self._working_suite = s
        return self._working_suite

    def reset(self):
        self._working_suite = None   # type: SweetSuite or None
        self._previous_tools = None  # type: list[SuiteTool] or None

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

    def load(self, path, as_import=False, re_resolve=True):
        """Load existing suite

        When loading suite, all contexts requests and .rxt files will be
        resolved and loaded.

        :param str path: Location to save current working suite
        :param bool as_import: If True, suite could not save over to where it
            was loaded from. Default is False.
        :param bool re_resolve: If True, all loaded contexts (.rxt) will be
            re-resolved as live contexts. Default is True.
        :return: None
        """

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
        self._previous_tools = list(self.iter_tools(visible_only=True))

        if re_resolve:
            suite.re_resolve_rxt_contexts()
        suite.load_path = None if as_import else os.path.realpath(path)

    def save(self, path, as_archived=False):
        """Save current working suite

        :param str path: Path to save the suite
        :param bool as_archived: Save suite as archived
        :return: None
        """
        release_root = sweetconfig.suite_roots.get(sweetconfig.release_root)
        non_local_required = \
            util.normpath(release_root) == os.path.dirname(util.normpath(path))

        self.sanity_check(non_local=non_local_required)
        # note: cannot save over if load_path is None
        self._suite.save(path, as_archived=as_archived)
        # run callback
        sweetconfig.on_suite_saved_callback(self._suite, path)

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

    def sanity_check(self, non_local=False):
        """Ensure suite is valid.

        :param non_local: Make sure all packages are non-local
        :type non_local: bool
        :return: None
        :raise SuiteOpError: If suite validation failed.
        """
        try:
            self._suite.validate()
        except SuiteError as e:
            raise SuiteOpError(e)

        if non_local:
            non_local_paths = util.normpaths(*rezconfig.nonlocal_packages_path)
            for ctx in self.iter_contexts():
                for variant in ctx.resolves:
                    norm_location = util.normpath(variant.resource.location)
                    if norm_location not in non_local_paths:
                        raise SuiteOpError(
                            "Non-local packages check has enabled, and found "
                            f"local package {variant.qualified_name!r} in "
                            f"context {ctx.name!r}."
                        )

    def get_description(self):
        """Get suite description
        :return: suite description string
        :rtype: str
        """
        return self._suite.description

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

    def resolve_context(self, requests):
        """Try resolving a context

        :param requests: List of strings or PackageRequest objects representing
            the request for resolving a context.
        :type requests: list[str or PackageRequest]
        :return: A RollingContext object
        :rtype: RollingContext
        """
        return RollingContext(requests)

    def add_context(self, name, context):
        """Add one resolved context to suite

        The context `name` must not exists in suite nor an empty string. And
        the `context` object must be a success resolved one.

        If inputs not able to meet the condition above, nothing will change
        and returns `None` with `SuiteOpWarning` issued (or error raised if
        warnings are being treated as error).

        :param str name: Name to store the context under.
        :param context: Context to add. Must be a success resolved context.
        :type context: RollingContext
        :return: None if failed, or a SuiteCtx that represents the context
            just being added.
        :rtype: None or SuiteCtx
        """
        assert isinstance(context, RollingContext)
        if self._suite.has_context(name):
            _warn("Context already in suite: %r" % name)
            return

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

        If update success, a `SuiteCtx` instance will be returned as update
        record.

        :param str name: The name of existing suite context.
        :param new_name: Rename context.
        :param context: Context to update. Must be a success resolved context.
        :param prefix: Change context prefix.
        :param suffix: Change context suffix.
        :param tool_name: The name of the tool in context `name`.
        :param new_alias: Change tool alias, `tool_name` must be given.
        :param set_hidden: Change tool visibility, `tool_name` must be given.
        :type new_name: str or None
        :type context: RollingContext or None
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

        if context is not None:
            assert isinstance(context, RollingContext)
            if not context.success:
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

        data = self._suite.contexts[ctx_name]
        return self._ctx_data_to_tuple(data)

    def re_resolve_rxt_contexts(self):
        """Re-resolve all contexts that loaded from .rxt files
        :return:
        """
        self._suite.re_resolve_rxt_contexts()

    def get_context(self, name):
        """Get a copy of context in suite

        :param str name: context name
        :return: A copy of the context
        :rtype: RollingContext
        """
        return self._suite.context(name).copy()

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

    def iter_contexts(self, ascending=False):
        """Iterate contexts in suite in priority ordered

        By default (descending ordered), the context that has higher priority
        will be iterated first.

        :param ascending: Iter contexts by priority in ascending order.
        :type ascending: bool or False
        :return: An SuiteCtx object iterator
        :rtype: collections.Iterator[SuiteCtx]
        """
        ctx_data = sorted(
            self._suite.contexts.values(), key=lambda x: x["priority"],
            reverse=not ascending
        )
        for d in ctx_data:
            yield self._ctx_data_to_tuple(d)

    def iter_tools(self, context_name=None, visible_only=False):
        """Iterate all tools in suite

        Suite tools will be iterated in following order:
            - Valid, not being hidden, not in conflict
            - Hidden
            - Shadowed (name/alias conflicts with other tool)
            - Missing (failed context or new one has different tools/aliases)

        A previously saved suite may have missing tools due to the request
        of the context is no longer resolvable in current condition.

        :param context_name: Only yield tools in this context.
        :type context_name: str or None
        :param visible_only: If True, only yield tools that are not
            hidden/shadowed/missing. Default False.
        :type visible_only: bool
        :return: An SuiteTool object iterator
        :rtype: collections.Iterator[SuiteTool]
        """
        self._suite.update_tools()
        _visible = set()

        def _match_context(d_):
            return context_name is None or context_name == d_["context_name"]

        status = Constants.TOOL_VALID
        for d in self._suite.tools.values():
            _visible.add(d["tool_alias"])
            if _match_context(d):
                yield self._tool_data_to_tuple(d, status=status)

        if visible_only:
            return

        status = Constants.TOOL_HIDDEN
        for d in self._suite.hidden_tools:
            if _match_context(d):
                yield self._tool_data_to_tuple(d, status=status)

        status = Constants.TOOL_SHADOWED
        for entries in self._suite.tool_conflicts.values():
            for d in entries:
                if _match_context(d):
                    yield self._tool_data_to_tuple(d, status=status)

        status = Constants.TOOL_MISSING
        for _tool in self._previous_tools or []:
            if _match_context(_tool.ctx_name):
                if _tool.alias not in _visible:
                    _tool.status = status
                    yield _tool

    def _ctx_tool_exists(self, context, tool_name):
        context_tools = context.get_tools(request_only=True)
        for _, tool_names in context_tools.values():
            if tool_name in tool_names:
                return True
        return False

    def _ctx_data_to_tuple(self, d):
        context = self._suite.context(d["name"])
        rq = [r for r in context.requested_packages()]
        rs = [r for r in context.resolved_packages]
        return SuiteCtx(
            name=d["name"],
            priority=d["priority"],
            prefix=d.get("prefix", ""),
            suffix=d.get("suffix", ""),
            requests=rq,
            resolves=rs,
            context=context,
        )

    def _tool_data_to_tuple(self, d, status=0):
        return SuiteTool(
            name=d["tool_name"],
            alias=d["tool_alias"],
            status=status,
            ctx_name=d["context_name"],
            # todo:
            #  A single tool could be given by multiple variants (same tool
            #  name in their `tools` property).
            #  When that happens, we can't for sure which actual executable
            #  will be executed (depends on which come first in PATH), so
            #  we must list them all out here.
            #  See `TestCore.test_tool_by_multi_packages`.
            variant=d["variant"],
            location=d["variant"].resource.location,
            uri=d["variant"].uri,
        )


class RollingContext(ResolvedContext):
    """A ResolvedContext subclass that suppress error in get_tools()

    This allows suite to bypass invalid context (a context loaded from a .rxt
    which becomes invalid) and continue to get tools from other contexts.

    If error raised in ResolvedContext.get_tools(), it will be raised after
    Suite._update_tools() completed.

    Also, a simple replacement for a failed context

    By "failed", it means a context failed
        1. when the resolve leads to non-existing package, or
        2. when trying to load a non-existing .rxt file.

    """

    def __init__(self, *args, **kwargs):
        self._is_broken = False
        self._err_on_get_tools = None
        try:
            super(RollingContext, self).__init__(*args, **kwargs)
        except Exception as e:
            r = self._get_broken(e, *args, **kwargs)
            self.__dict__.update(r.__dict__)

    @classmethod
    def _get_broken(cls, e, *args, **kwargs):
        r = cls.__new__(cls)
        with _BrokenResolver.patch_resolver():
            ResolvedContext.__init__(r, *args, **kwargs)
        r._is_broken = True
        r.failure_description = str(e)
        r._resolved_packages = []
        r.graph_string = "{}"
        return r

    @classmethod
    def from_dict(cls, d, identifier_str=None):
        r = super(RollingContext, cls).from_dict(d, identifier_str)
        r._is_broken = False
        r._err_on_get_tools = None
        return r

    @classmethod
    def load(cls, path):
        try:
            return super(RollingContext, cls).load(path)
        except Exception as e:
            return cls._get_broken(e, package_requests=[])

    def get_tools(self, request_only=False):
        self._err_on_get_tools = None
        try:
            return super(RollingContext, self).get_tools(request_only)
        except Exception as e:
            self._err_on_get_tools = e
            name = self.suite_context_name or ""
            log.error(f"Failed to get tools from context {name!r}: {str(e)}")
            return {}

    @ResolvedContext._on_success
    def validate(self):
        if self._is_broken:
            raise ResolvedContextError(
                f"This is a broken context: {self.failure_description}")
        super(RollingContext, self).validate()

    @property
    def usable(self):
        return self.success and self._err_on_get_tools is None

    @property
    def broken(self):
        return self._is_broken

    @property
    def err_on_get_tools(self):
        return self._err_on_get_tools

    def print_info(self, buf=sys.stdout, *args, **kwargs):
        if self._is_broken:
            self._print_broken_info(buf=buf, *args, **kwargs)
        else:
            super(RollingContext, self).print_info(buf=buf, *args, **kwargs)

    def _print_broken_info(self, buf=sys.stdout, *args, **kwargs):
        from rez.utils.colorize import warning
        from rez.resolved_context import Printer
        super(RollingContext, self).print_info(buf, *args, **kwargs)
        # the Printer may gets patched in GUI for writing HTML formatted log
        _pr = Printer(buf)
        _pr("This is a broken context:", warning)
        _pr("A context that error out during the resolve.", warning)

    @classmethod
    @contextmanager
    def patch_rolling_context(cls):
        from rez import suite, resolved_context
        setattr(suite, "ResolvedContext", cls)
        setattr(resolved_context, "ResolvedContext", cls)
        yield
        setattr(suite, "ResolvedContext", ResolvedContext)
        setattr(resolved_context, "ResolvedContext", ResolvedContext)


class Storage(object):
    """Suite storage"""
    ArchivedFlag = ".archived"

    def __init__(self, roots=None):
        """
        :param roots: Storage roots, branch name as key and path as value.
        :type roots: dict
        """
        roots = roots or sweetconfig.suite_roots  # type: dict
        assert isinstance(roots, MutableMapping), (
            f"Expect dict-like object, got {type(roots)}"
        )  # note: this is for the arg `roots`, there's type check in rezconfig

        self._roots = roots

    def __repr__(self):
        return "%s(%s)" % (
            self.__class__.__name__,
            ", ".join("%s=%s" % (b, path) for b, path in self._roots)
        )

    @classmethod
    def set_archived(cls, suite_path, state):
        """Mark a saved-suite as archived or not

        :param str suite_path: Path where suite is saved
        :param bool state: Archive state
        :return: True if archive state changed or False if not
        :rtype: bool
        """
        archive_flag = os.path.join(suite_path, cls.ArchivedFlag)
        is_archived = os.path.isfile(archive_flag)

        if not state and is_archived:
            try:
                os.remove(archive_flag)
            except Exception as e:
                log.critical(f"Unarchive suite failed: {str(e)}")
            else:
                return True

        elif state and not is_archived:
            try:
                with open(archive_flag, "w") as f:
                    f.write("")
            except Exception as e:
                log.critical(f"Archive suite failed: {str(e)}")
            else:
                return True

        return False

    def branches(self):
        """Get current suite storage branch names

        :return: List of suite storage branch names.
        :rtype: list
        """
        return list(self._roots.keys())

    def suite_path(self, branch, name):
        """Compose suite directory path

        :param branch: Suite storage branch
        :param name: Suite name
        :type branch: str
        :type name: str
        :return: Suite directory path
        :rtype: str
        """
        try:
            root = self._roots[branch]
        except KeyError:
            raise SuiteIOError("Unknown storage branch: %r" % branch)

        return os.path.join(root, name)

    def iter_saved_suites(self, branch=None, archived=False):
        """Iter existing suites withing given roots

        :param branch: Suite storage branch. Iter all branches if not given.
        :param bool archived: Iter archived suite. Default False.
        :type branch: str or None
        :return: A SavedSuite object iterator
        :rtype: collections.Iterator[SavedSuite]
        """
        # todo:
        #   implement a package release hook that checks if tools consists.

        for b, root in self._roots.items():
            if branch and b != branch:
                continue

            if not os.path.isdir(root):
                continue

            for name in os.listdir(root):
                path = os.path.join(root, name)
                filepath = os.path.join(path, "suite.yaml")

                if os.path.isfile(filepath):
                    archive_flag = os.path.join(path, self.ArchivedFlag)
                    is_archived = os.path.isfile(archive_flag)
                    _keys = dict(
                        name=name,
                        branch=b,
                        path=path,
                        suite=None,  # lazy load
                    )
                    if archived and is_archived:
                        yield SavedSuite(archived=True, **_keys)
                    elif not archived and not is_archived:
                        yield SavedSuite(archived=False, **_keys)


class InstalledPackages(object):
    """Utility for iterating installed rez packages in given paths
    """

    def __init__(self, packages_path=None):
        """
        :param packages_path: Paths to look for packages. If not provide,
            use `rezconfig.packages_path` by default.
        :type packages_path: list[str] or None
        """
        self._paths = packages_path or rezconfig.packages_path
        self._non_local = util.normpaths(*rezconfig.nonlocal_packages_path)

    @property
    def packages_path(self):
        """Returns package lookup paths that this instance is using

        :return: Current paths for finding packages.
        :rtype: list[str]
        """
        return self._paths

    def clear_caches(self, location=None):
        """Clear repository cache for current session to spot new package

        :param location: One single package path to clear. Clear cache of all
            paths (`packages_path`) if not given.
        :type location: str or None
        :return: None
        """
        paths = [location] if location else self._paths

        for path in paths:
            repo = package_repository_manager.get_repository(path)
            repo.clear_caches()

    def iter_families(self, location=None):
        """Iter package families

        Note that same family may get yielded multiple times since they
        exists in multiple locations, e.g. from 'install' and 'release'.

        :param location: One single package path to look for. Loop over all
            paths (`packages_path`) if not given.
        :type location: str or None
        :return: An iterator that yields `PkgFamily` objects
        :rtype: collections.Iterator[PkgFamily]
        """
        paths = [location] if location else self._paths

        for family in iter_package_families(paths=paths):
            location = family.resource.location
            location = "{}@{}".format(family.repository.name(), location)
            # for repository type other than 'filesystem', e.g. 'memory'

            yield PkgFamily(
                name=family.name,
                location=location,
            )

    def iter_versions(self, name, location=None):
        """Iter package versions

        :param name: Package name
        :param location: One single package path to look for. Loop over all
            paths (`packages_path`) if not given.
        :type name: str
        :type location: str or None
        :return: An iterator that yields `PkgVersion` objects
        :rtype: collections.Iterator[PkgVersion]
        """
        paths = [location] if location else self._paths

        _cache = dict()
        for p in iter_packages(name, paths=paths):
            _l = p.resource.location
            if _l in _cache:
                norm_location = _cache[_l]
            else:
                norm_location = util.normpath(_l)
                _cache[_l] = norm_location

            is_nonlocal = norm_location in self._non_local

            yield PkgVersion(
                name=name,
                version=p.version,
                qualified=p.qualified_name,
                requires=[str(r) for r in p.requires or []],
                variants=[[str(r) for r in var] for var in p.variants or []],
                tools=p.tools or [],
                uri=p.uri,
                timestamp=p.timestamp,
                location=norm_location,
                is_nonlocal=is_nonlocal,
            )


def re_resolve_rxt(context):
    """Re-resolve context loaded from .rxt file

    This takes following entries from input context to resolve a new one:
        - package_requests
        - timestamp
        - package_paths
        - package_filters
        - package_orderers
        - building

    :param context: .rxt loaded context
    :type context: ResolvedContext
    :return: new resolved context
    :rtype: RollingContext
    :raises AssertionError: If no context.load_path (not loaded from .rxt)
    """
    assert context.load_path, "Not a loaded context."
    rxt = context
    return RollingContext(
        package_requests=rxt.requested_packages(),
        timestamp=rxt.requested_timestamp,
        package_paths=rxt.package_paths,
        package_filter=rxt.package_filter,
        package_orderers=rxt.package_orderers,
        building=rxt.building,
    )


class _Suite(Suite):
    @classmethod
    def from_dict(cls, d):
        s = cls.__new__(cls)
        s.load_path = None
        s.tools = None
        s.tool_conflicts = None
        s.contexts = d["contexts"]
        if s.contexts:
            s.next_priority = max(x["priority"]
                                  for x in s.contexts.values()) + 1
        else:
            s.next_priority = 1
        return s


class SweetSuite(_Suite):
    """A collection of contexts. (run tools in live resolved context)

    A suite is a collection of contexts. A suite stores its contexts in a
    single directory, and creates wrapper scripts for each tool in each context,
    which it stores into a single bin directory. When a tool is invoked, it
    executes the actual tool in its associated context. When you add a suite's
    bin directory to PATH, you have access to all these tools, which will
    automatically run in correctly configured environments.

    Tool clashes can occur when a tool of the same name is present in more than
    one context. When a context is added to a suite, or prefixed/suffixed, that
    context's tools override tools from other contexts.

    There are several ways to avoid tool name clashes:
    - Hide a tool. This removes it from the suite even if it does not clash;
    - Prefix/suffix a context. When you do this, all the tools in the context
      have the prefix/suffix applied;
    - Explicitly alias a tool using the `alias_tool` method. This takes
      precedence over context prefix/suffixing.

    Additional entries SweetSuite's suite.yaml:
        - description
        - is_live
    """
    def __init__(self):
        super(SweetSuite, self).__init__()
        self._description = ""
        self._is_live = True

    def context(self, name):
        """Get a context.
        :param name:
        :return:
        """
        with RollingContext.patch_rolling_context():
            return super(SweetSuite, self).context(name)

    def save(self, path, as_archived=False, verbose=False):
        """Save the suite to disk.

        Args:
            path (str): Path to save the suite to. If a suite is already saved
                at `path`, then it will be overwritten. Otherwise, if `path`
                exists, an error is raised.
            as_archived (bool): Save suite as archived
            verbose (bool): Show more messages.
        """
        if verbose and self._is_live:
            print("saving live suite...")

        # todo:
        #   1. instead of wiping it all out, cherry-pick tools to update/remove
        #       by requests.
        #   2. make a copy of current suite (in timestamp dir)

        path = os.path.realpath(path)
        if os.path.exists(path):
            if self.load_path and self.load_path == path:
                if verbose:
                    print("saving over previous suite...")
                for context_name in self.context_names:
                    self.context(context_name)  # load before dir deleted

                forceful_rmtree(path)
            else:
                raise SuiteError("Cannot save, path exists: %r" % path)

        os.makedirs(path)
        if as_archived:
            Storage.set_archived(path, state=True)

        # write suite data
        data = self.to_dict()
        filepath = os.path.join(path, "suite.yaml")
        with open(filepath, "w") as f:
            f.write(dump_yaml(data))

        # write contexts
        for context_name in self.context_names:
            context = self.context(context_name)
            context._set_parent_suite(path, context_name)  # noqa
            self._save_context_rxt(context_name, context, path)

        # create alias wrappers
        tools_path = os.path.join(path, "bin")
        os.makedirs(tools_path)
        if verbose:
            print("creating alias wrappers in %r..." % tools_path)

        tools = self.get_tools()
        for tool_alias, d in tools.items():
            tool_name = d["tool_name"]
            context_name = d["context_name"]

            data = self._context(context_name)
            prefix_char = data.get("prefix_char")

            if verbose:
                print("creating %r -> %r (%s context)..."
                      % (tool_alias, tool_name, context_name))
            filepath = os.path.join(tools_path, tool_alias)

            if self._is_live:
                context = data["context"]
                requests = [str(r) for r in context.requested_packages()]
                # todo: instead of parsing requests, load the rxt and re-resolve
                #   again.
                kwargs = {
                    "module": ("command", "sweet"),  # rez plugin
                    "func_name": "_FWD__invoke_suite_tool_alias_in_live",
                    "package_requests": requests,
                    "context_name": context_name,
                    "tool_name": tool_name,
                    "prefix_char": prefix_char,
                }
            else:
                kwargs = {
                    "module": "suite",
                    "func_name": "_FWD__invoke_suite_tool_alias",
                    "context_name": context_name,
                    "tool_name": tool_name,
                    "prefix_char": prefix_char,
                }

            create_forwarding_script(filepath, **kwargs)

    def to_dict(self):
        """Parse suite into dict
        :return:
        :rtype: dict
        """
        data = super(SweetSuite, self).to_dict()
        data["description"] = self._description
        data["live_resolve"] = self._is_live
        return data

    @classmethod
    def from_dict(cls, d):
        """Parse dict into suite
        :return:
        :rtype: SweetSuite
        """
        s = super(SweetSuite, cls).from_dict(d)
        s._description = d.get("description", "")
        s._is_live = d.get("live_resolve", False)
        return s

    def add_context(self, name, context, prefix_char=None):
        assert isinstance(context, RollingContext)
        if not name:
            # todo: implement filesystem valid name check and push the
            #   change into nerdvegas/rez.
            raise SuiteError("Invalid context name.")
        super(SweetSuite, self).add_context(name, context, prefix_char)

    # New methods that are not in rez.suite.Suite
    #

    def _save_context_rxt(self, name, context, path):
        """Save context .rxt

        :param name: context name
        :param context: a resolved context object
        :param path: path to save the context
        :type name: str
        :type context: ResolvedContext
        :type path: str
        :return:
        """
        filepath = self._context_path(name, path)
        _dir_path = os.path.dirname(filepath)
        if not os.path.isdir(_dir_path):
            os.makedirs(_dir_path)
        context.save(filepath)

    def set_live(self, value):
        self._is_live = value

    def is_live(self):
        return self._is_live

    @property
    def description(self):
        return self._description

    def set_description(self, text):
        self._description = text

    def has_context(self, name):
        """Is context name exists in suite ?"""
        return name in self.contexts

    def rename_context(self, old_name, new_name):
        """Rename context

        Tools will be flushed after rename.

        Args:
            old_name (str): Original context name.
            new_name (str): New context name.

        """
        if old_name not in self.contexts:
            raise SuiteError("No such context in suite: %r" % old_name)
        if new_name in self.contexts:
            raise SuiteError("Duplicated name in suite: %r" % new_name)
        if not new_name:
            raise SuiteError("Invalid context name.")

        data = self.contexts.pop(old_name)
        data["name"] = new_name
        self.contexts[new_name] = data

        self._flush_tools()

    def update_context(self, name, context):
        """Update one context in the suite

        If `name` exist in suite, `context` will be replaced and tools
        be reset. This is to avoid removing and adding back context under
        same name when re-requesting packages, which will lead to context
        priority change.

        Args:
            name (str): Name to store the context under.
            context (RollingContext): Context to add/update.

        """
        assert isinstance(context, RollingContext)
        if not context.success:
            raise SuiteError("Context is not resolved: %r" % name)

        if name not in self.contexts:
            raise SuiteError("No such context in suite: %r" % name)

        data = self.contexts[name]
        aliases = dict()
        hidden = set()

        # preserving context priority, prefix, suffix, and tools'
        # aliases/hidden state
        context_tools = context.get_tools(request_only=True)
        for _, tool_names in context_tools.values():
            for tool_name in tool_names:
                if tool_name in data["tool_aliases"]:
                    aliases[tool_name] = data["tool_aliases"][tool_name]
                if tool_name in data["hidden_tools"]:
                    hidden.add(tool_name)

        data["context"] = context.copy()
        data["tool_aliases"] = aliases
        data["hidden_tools"] = hidden
        if context.load_path:
            data["loaded"] = True
        else:
            data.pop("loaded", None)

        self._flush_tools()

    def re_resolve_rxt_contexts(self):
        """Re-resolve all contexts that loaded from .rxt files
        :return:
        """
        for name in list(self.contexts.keys()):
            context = self.context(name)
            if context.load_path:
                self.update_context(name, re_resolve_rxt(context))

    def _update_tools(self):
        report_err = self.tools is None

        super(SweetSuite, self)._update_tools()

        if not report_err:
            return
        for data in self.contexts.values():
            context = data.get("context")  # type: RollingContext
            if context is None:
                continue  # possibly not yet loaded
            if context.success:
                if not context.usable:
                    raise context.err_on_get_tools
            else:
                raise ResolvedContextError(context.failure_description)

    # Exposing protected member that I'd like to use.
    update_tools = _update_tools
    flush_tools = Suite._flush_tools


class _BrokenResolver(object):

    def __init__(self, *_, **__):
        self.status = ResolverStatus.failed
        self.solve_time = 0.0
        self.load_time = 0.0
        self.failure_description = "A broken resolve."
        self.graph = None
        self.from_cache = False
        self.resolved_packages = ()
        self.resolved_ephemerals = ()

    def solve(self):
        pass

    @classmethod
    @contextmanager
    def patch_resolver(cls):
        from rez import resolved_context
        _Resolver = getattr(resolved_context, "Resolver")
        setattr(resolved_context, "Resolver", cls)
        yield
        setattr(resolved_context, "Resolver", _Resolver)
