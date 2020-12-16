
import os
from rez.utils.execution import create_forwarding_script
from rez.packages import iter_package_families, iter_packages
from rez.resolved_context import ResolvedContext
from rez import suite
from rez.config import config
from rez.vendor import yaml
from rez.vendor.yaml.error import YAMLError

Suite = suite.Suite
SuiteError = suite.SuiteError


class SweetSuite(Suite):

    def __init__(self, live=True):
        super(SweetSuite, self).__init__()
        self.description = ""
        self._is_live = live

    def add_description(self, text):
        self.description = text

    def is_live(self):
        return self._is_live

    def to_dict(self):
        data = super(SweetSuite, self).to_dict()
        data["description"] = self.description
        data["live_resolve"] = self._is_live
        return data

    @classmethod
    def from_dict(cls, d):
        suite.Suite = SweetSuite
        s = super(SweetSuite, cls).from_dict(d)
        s.description = d.get("description", "")
        s._is_live = d.get("live_resolve", False)
        return s

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

    def save(self, path, verbose=False):
        super(SweetSuite, self).save(path, verbose=verbose)
        if self._is_live:
            # remove .rxt ?
            # override bin
            tools_path = os.path.join(path, "bin")

            tools = self.get_tools()
            for tool_alias, d in tools.items():
                tool_name = d["tool_name"]
                context_name = d["context_name"]

                data = self._context(context_name)
                context = data["context"]
                requests = [str(r) for r in context.requested_packages()]
                prefix_char = data.get("prefix_char")

                if verbose:
                    print("(live) creating %r -> %r (%s context)..."
                          % (tool_alias, tool_name, context_name))
                filepath = os.path.join(tools_path, tool_alias)

                create_forwarding_script(
                    filepath,
                    module=("build_system", "sweet"),  # rez plugin
                    func_name="_FWD__invoke_suite_tool_alias_in_live",
                    package_requests=requests,
                    context_name=context_name,
                    tool_name=tool_name,
                    prefix_char=prefix_char,
                )


def read_suite_description(filepath):
    """
    Args:
        filepath (str): path to suite.yaml
    Returns:
        str
    """
    try:
        with open(filepath) as f:
            data = yaml.load(f.read(), Loader=yaml.FullLoader)
    except YAMLError:
        pass
    else:
        return data.get("description", "")


__all__ = [
    "iter_package_families",
    "iter_packages",
    "ResolvedContext",
    "SweetSuite",
    "SuiteError",
    "config",
    "read_suite_description",
]
