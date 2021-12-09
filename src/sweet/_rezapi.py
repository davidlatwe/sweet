
import os
from rez.utils.filesystem import forceful_rmtree
from rez.utils.execution import create_forwarding_script
from rez.utils.yaml import dump_yaml
from rez.packages import iter_package_families, iter_packages
from rez.resolved_context import ResolvedContext
from rez import suite
from rez.config import config
from rez.vendor import yaml
from rez.vendor.yaml.error import YAMLError  # noqa

Suite = suite.Suite
SuiteError = suite.SuiteError


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

    def __init__(self):
        super(SweetSuite, self).__init__()
        self.description = ""
        self._is_live = True
        self._saved_tools = None
        self._saved_requests = None

    def context(self, name):
        """Get a context.

        Args:
            name (str): Name to store the context under.

        Returns:
            `ResolvedContext` object.
        """
        data = self._context(name)
        context = data.get("context")
        if context:
            return context

        assert self.load_path
        context_path = self._context_path(name, self.load_path)
        saved_context = None
        if os.path.isfile(context_path):
            saved_context = ResolvedContext.load(context_path)

        if self._is_live:
            try:
                # note: live resolved `context.load_path` is None
                context = ResolvedContext(self._saved_requests[name])
            except Exception as e:
                if saved_context is None:
                    raise e
                # fallback to saved .rxt
                context = saved_context

            else:
                context._set_parent_suite(self.load_path, name)  # noqa
                if context != saved_context:
                    self._save_context(name, context, self.load_path)

        else:
            context = saved_context

        data["context"] = context
        data["loaded"] = True
        return context

    def save(self, path, verbose=False):
        """Save the suite to disk.

        Args:
            path (str): Path to save the suite to. If a suite is already saved
                at `path`, then it will be overwritten. Otherwise, if `path`
                exists, an error is raised.
            verbose (bool): Show more messages.
        """
        if verbose and self._is_live:
            print("saving live suite...")

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

        else:
            os.makedirs(path)

        # write suite data
        data = self.to_dict()
        filepath = os.path.join(path, "suite.yaml")
        with open(filepath, "w") as f:
            f.write(dump_yaml(data))

        # write contexts
        for context_name in self.context_names:
            context = self.context(context_name)
            context._set_parent_suite(path, context_name)  # noqa
            self._save_context(
                context_name, context, path, verbose=verbose
            )

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
        data = super(SweetSuite, self).to_dict()
        data["description"] = self.description
        data["live_resolve"] = self._is_live
        data["tools"] = {
            cname: [
                tool_alias for tool_alias, d in self.get_tools().items()
                if cname == d["context_name"]
            ]
            for cname in self.context_names
        }
        data["requests"] = {
            cname: [
                str(r) for r in self.context(cname).requested_packages()
            ]
            for cname in self.context_names
        }
        return data

    @classmethod
    def from_dict(cls, d):
        s = super(SweetSuite, cls).from_dict(d)
        s.description = d.get("description", "")
        s._is_live = d.get("live_resolve", False)
        s._saved_tools = d.get("tools")
        s._saved_requests = d.get("requests")
        return s

    # New methods that are not in rez.suite.Suite
    #

    def _save_context(self, name, context, path, verbose=False):
        filepath = self._context_path(name, path)
        if verbose:
            print("writing %r..." % filepath)

        dir_path = os.path.dirname(filepath)
        if not os.path.isdir(dir_path):
            os.makedirs(dir_path)

        context.save(filepath)

    def saved_tools(self):
        return self._saved_tools

    def is_live(self):
        return self._is_live

    def add_description(self, text):
        self.description = text

    def sorted_context_names(self):
        ctxs = self.contexts
        return sorted(ctxs.keys(), key=lambda x: ctxs[x]["priority"])

    def read_context(self, name, entry, default=None):
        data = self._context(name)
        return data.get(entry, default)

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
            raise SuiteError("Context not in suite: %r" % old_name)

        data = self.contexts.pop(old_name)
        data["name"] = new_name
        self.contexts[new_name] = data
        self._flush_tools()

    def update_context(self, name, context):
        """Add or update a context to the suite

        If `name` exist in suite, `context` will be replaced and tools
        be reset. This is to avoid removing and adding back context under
        same name when re-requesting packages, which will lead to context
        priority change.

        Args:
            name (str): Name to store the context under.
            context (ResolvedContext): Context to add/update.

        """
        # so we don't need to worry about priority change if remove and re-add
        if not context.success:
            raise SuiteError("Context is not resolved: %r" % name)

        if name in self.contexts:
            # update with priority preserved
            data = self.contexts[name]
            data["context"] = context.copy()
            data["tool_aliases"] = {}
            data["hidden_tools"] = set()
            self._flush_tools()
        else:
            self.add_context(name, context)

    # Exposing protected member that I'd like to use.
    update_tools = Suite._update_tools


def read_suite_description(filepath):
    """
    Args:
        filepath (str): path to suite.yaml
    Returns:
        str
    """
    try:
        with open(filepath) as f:
            data = yaml.load(f.read(), Loader=yaml.FullLoader)  # noqa
    except YAMLError:
        pass
    else:
        return data.get("description", "")


__all__ = [
    "iter_package_families",
    "iter_packages",
    "read_suite_description",

    "config",
    "SuiteError",

    "ResolvedContext",
    "SweetSuite",
]
