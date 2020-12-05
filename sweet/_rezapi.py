
from rez.packages import iter_package_families, iter_packages
from rez.resolved_context import ResolvedContext
from rez.suite import Suite, SuiteError
from rez.config import config


class SweetSuite(Suite):

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


__all__ = [
    "iter_package_families",
    "iter_packages",
    "ResolvedContext",
    "SweetSuite",
    "SuiteError",
    "config",
]
