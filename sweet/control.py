
import os
from collections import defaultdict
from Qt5 import QtCore
from . import _rezapi as rez
from .search.model import PackageModel
from .sphere.model import ToolModel


class Controller(QtCore.QObject):

    def __init__(self, parent=None):
        super(Controller, self).__init__(parent=parent)

        state = {
            "suite": rez.SweetSuite(),
            "suiteName": "",
            "contextName": dict(),
            "contextRequests": defaultdict(list),  # success requests history
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
        history = self._state["contextRequests"][id_]
        tool = self._models["contextTool"][id_]
        if not name:
            print("Naming context first.")
            return

        try:
            context = rez.ResolvedContext(requests)
        except Exception as e:
            print(e)
            # dirty context
        else:
            if not context.success:
                # dirty context
                print("Context resolving failed.")
            else:
                tool.clear()
                context_tools = context.get_tools(request_only=True)
                for pkg_name, (variant, tools) in context_tools.items():
                    tool.add_items(tools)
                history.append(requests)
                suite.update_context(name, context)
                self.defer_update_suite_tools()

    def on_context_removed(self, id_):
        self._models["contextTool"].pop(id_)
        self._state["contextRequests"].pop(id_)
        name = self._state["contextName"].pop(id_)
        suite = self._state["suite"]
        if suite.has_context(name):
            suite.remove_context(name)
            self.defer_update_suite_tools()

    def on_context_named(self, id_, name):
        suite = self._state["suite"]
        names = self._state["contextName"]
        old_name = names[id_]
        names[id_] = name
        if suite.has_context(old_name):
            suite.rename_context(old_name, name)
            self.defer_update_suite_tools()

    def on_context_prefix_changed(self, id_, prefix):
        tool = self._models["contextTool"][id_]
        name = self._state["contextName"][id_]
        suite = self._state["suite"]
        tool.set_prefix(prefix)
        suite.set_context_prefix(name, prefix)
        self.defer_update_suite_tools()

    def on_context_suffix_changed(self, id_, suffix):
        tool = self._models["contextTool"][id_]
        name = self._state["contextName"][id_]
        suite = self._state["suite"]
        tool.set_suffix(suffix)
        suite.set_context_suffix(name, suffix)
        self.defer_update_suite_tools()

    def on_context_tool_alias_changed(self, id_, tool, alias):
        name = self._state["contextName"][id_]
        suite = self._state["suite"]
        if alias:
            suite.alias_tool(name, tool, alias)
        else:
            suite.unalias_tool(name, tool)
        self.defer_update_suite_tools()

    def on_context_tool_hide_changed(self, id_, tool, hide):
        name = self._state["contextName"][id_]
        suite = self._state["suite"]
        if hide:
            suite.hide_tool(name, tool)
        else:
            suite.unhide_tool(name, tool)
        self.defer_update_suite_tools()

    def on_tool_updated(self):
        # TODO: block and unblock gui ?
        suite = self._state["suite"]
        suite.update_tools()

        # update tool models
        for id_, name in self._state["contextName"].items():
            conflicts = set()
            tool = self._models["contextTool"][id_]

            for exposed in tool.iter_exposed_tools():
                for entry in suite.get_alias_conflicts(exposed) or []:
                    if entry["context_name"] == name:
                        conflicts.add(exposed)

            tool.set_conflicting(conflicts)

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
            paths = rez.config.nonlocal_packages_path

        for family in rez.iter_package_families(paths=paths):
            name = family.name
            path = family.resource.location

            for package in rez.iter_packages(name, paths=[path]):
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