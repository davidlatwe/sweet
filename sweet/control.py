
import os
from Qt5 import QtCore
from rez.packages_ import iter_package_families, iter_packages
from rez.resolved_context import ResolvedContext
from rez.suite import Suite, SuiteError
from rez.config import config

from .search.model import PackageModel
from .sphere.model import ToolModel


class Controller(QtCore.QObject):

    def __init__(self, parent=None):
        super(Controller, self).__init__(parent=parent)

        state = {
            "suite": Suite(),
            "suiteName": "",
            "contextName": dict(),
        }

        timers = {
            "toolUpdate": QtCore.QTimer(self),
            "packageSearch": QtCore.QTimer(self),
        }

        models = {
            "package": PackageModel(),
            "contextTool": dict(),  # ToolModel per context
        }

        timers["packageSearch"].timeout.connect(self.on_package_searched)
        timers["toolUpdate"].timeout.connect(self.on_tool_updated)

        self._state = state
        self._timers = timers
        self._models = models

    @property
    def state(self):
        return self._state

    @property
    def models(self):
        return self._models

    def register_context_draft(self, id_):
        self._state["contextName"][id_] = ""
        self._models["contextTool"][id_] = ToolModel()

    def defer_search_packages(self, on_time=50):
        timer = self._timers["packageSearch"]
        timer.setSingleShot(True)
        timer.start(on_time)

    def defer_update_suite_tools(self, on_time=500):
        timer = self._timers["toolUpdate"]
        timer.setSingleShot(True)
        timer.start(on_time)

    def on_package_searched(self):
        self._models["package"].reset(self.iter_packages())

    def on_context_requested(self, id_, requests):
        suite = self._state["suite"]
        name = self._state["contextName"][id_]
        if not name:
            print("Naming context first.")
            return

        try:
            suite.remove_context(name)  # TODO: context priority will changed
        except SuiteError:
            pin_priority = False
        else:
            pin_priority = True

        tool = self._models["contextTool"][id_]
        tool.clear()

        try:
            context = ResolvedContext(requests)
        except Exception as e:
            print(e)
        else:
            if context.success:
                self._state["suite"].add_context(name, context)
            else:
                print("Context resolving failed.")

        finally:
            self.defer_update_suite_tools()

    def on_context_named(self, id_, name):
        self._state["contextName"][id_] = name

    def on_context_removed(self, id_):
        name = self._state["contextName"].pop(id_)
        if name:
            suite = self._state["suite"]
            try:
                suite.remove_context(name)
            except SuiteError:
                pass  # not yet been resolved hence not added into suite
            else:
                self.defer_update_suite_tools()

    def on_context_prefix_changed(self, id_, prefix):
        name = self._data["addedContext"][id_]
        suite = self._data["suite"]
        suite.set_context_prefix(name, prefix)
        self.defer_update_suite_tools()

    def on_context_suffix_changed(self, id_, suffix):
        name = self._data["addedContext"][id_]
        suite = self._data["suite"]
        suite.set_context_suffix(name, suffix)
        self.defer_update_suite_tools()

    def on_context_tool_alias_changed(self, id_, tool, alias):
        name = self._data["addedContext"][id_]
        suite = self._data["suite"]
        if alias:
            suite.alias_tool(name, tool, alias)
        else:
            suite.unalias_tool(name, tool)
        self.defer_update_suite_tools()

    def on_context_tool_hide_changed(self, id_, tool, hide):
        name = self._data["addedContext"][id_]
        suite = self._data["suite"]
        if hide:
            suite.hide_tool(name, tool)
        else:
            suite.unhide_tool(name, tool)
        self.defer_update_suite_tools()

    def on_tool_updated(self):
        # TODO: block and unblock gui ?
        # TODO: block suite save if has conflicts
        conflicts = self._state["suite"].get_conflicting_aliases()
        # update tool models
        for context_w in self._contexts.values():
            context_w.set_conflicting(conflicts)
            # Should change to use `get_alias_conflicts`, so the affect of
            # context priority can properly shown.

    def on_suite_saved(self):
        name = self._state["suiteName"]
        if name:
            self._state["suite"].save(os.path.expanduser("~/%s" % name))
        else:
            print("Naming suite first.")

    def iter_packages(self, no_local=False):
        paths = None
        seen = dict()

        if no_local:
            paths = config.nonlocal_packages_path

        for family in iter_package_families(paths=paths):
            name = family.name
            path = family.resource.location

            for package in iter_packages(name, paths=[path]):
                qualified_name = package.qualified_name

                if qualified_name in seen:
                    seen[qualified_name]["locations"].append(path)
                    continue

                doc = {
                    "family": name,
                    "version": str(package.version),
                    "uri": package.uri,
                    "tools": package.tools or [],
                    "qualified_name": qualified_name,
                    "timestamp": package.timestamp,
                    "locations": [path],
                }
                seen[qualified_name] = doc

                yield doc
