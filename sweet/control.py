
import os
from .vendor.Qt5 import QtCore
from . import _rezapi as rez
from .search.model import PackageModel
from .solve.model import ResolvedPackageModel, EnvironmentModel
from .sphere.model import ToolModel
from . import sweetconfig


class Controller(QtCore.QObject):

    def __init__(self, storage, parent=None):
        super(Controller, self).__init__(parent=parent)

        state = {
            "suite": rez.SweetSuite(),
            "suiteDir": "",
            "suiteName": "",
            "contextName": dict(),
            "contextRequests": dict(),  # success requests history
        }

        timers = {
            "toolUpdate": QtCore.QTimer(self),
            "packageSearch": QtCore.QTimer(self),
        }

        models = {
            "package": PackageModel(),
            # models per context
            "contextPackages": dict(),
            "contextEnvironment": dict(),
            "contextTool": dict(),
        }

        timers["packageSearch"].timeout.connect(self.on_package_searched)
        timers["toolUpdate"].timeout.connect(self.on_tool_updated)

        self._state = state
        self._timers = timers
        self._models = models
        self._storage = storage

    @property
    def state(self):
        return self._state

    @property
    def models(self):
        return self._models

    def store(self, key, value):
        """Write to persistent storage

        Arguments:
            key (str): Name of variable
            value (object): Any datatype

        """
        self._storage.setValue(key, value)

    def retrieve(self, key, default=None):
        """Read from persistent storage

        Arguments:
            key (str): Name of variable
            default (any): default value if key not found

        """
        value = self._storage.value(key)

        if value is None:
            value = default

        # Account for poor serialisation format
        # TODO: Implement a better format
        true = ["2", "1", "true", True, 1, 2]
        false = ["0", "false", False, 0]

        if value in true:
            value = True

        if value in false:
            value = False

        return value

    def register_context_draft(self, id_):
        self._state["contextName"][id_] = ""
        self._state["contextRequests"][id_] = []
        self._models["contextPackages"][id_] = ResolvedPackageModel()
        self._models["contextEnvironment"][id_] = EnvironmentModel()
        self._models["contextTool"][id_] = ToolModel()

        # we need to put an empty context on draft created, so the priority
        # bump can be matched properly.
        suite = self._state["suite"]
        empty = rez.ResolvedContext([])
        suite.add_context(id_, empty)

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
        resolved = self._models["contextPackages"][id_]
        env = self._models["contextEnvironment"][id_]
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
                resolved.clear()
                env.clear()
                tool.clear()
                history.append(requests)

                context_tools = context.get_tools(request_only=True)
                for pkg_name, (variant, tools) in context_tools.items():
                    tool.add_items(tools)

                resolved.add_items(context.resolved_packages)
                env.load(context.get_environ())

                # Use context id as name during suite editing to avoid name
                # conflict when renaming context aggressively.
                # Hint for future tests:
                #   * contexts named as "app" and "apple".
                #   * triggering rename on widget textChanged signal.
                suite.update_context(id_, context)
                self.defer_update_suite_tools()

    def on_context_removed(self, id_):
        self._models["contextTool"].pop(id_)
        self._models["contextPackages"].pop(id_)
        self._models["contextEnvironment"].pop(id_)
        self._state["contextName"].pop(id_)
        self._state["contextRequests"].pop(id_)
        suite = self._state["suite"]
        if suite.has_context(id_):
            suite.remove_context(id_)
            self.defer_update_suite_tools()

    def on_context_named(self, id_, name):
        self._state["contextName"][id_] = name

    def on_context_bumped(self, id_):
        suite = self._state["suite"]
        suite.bump_context(id_)
        self.defer_update_suite_tools()

    def on_context_prefix_changed(self, id_, prefix):
        tool = self._models["contextTool"][id_]
        suite = self._state["suite"]
        tool.set_prefix(prefix)
        suite.set_context_prefix(id_, prefix)
        self.defer_update_suite_tools()

    def on_context_suffix_changed(self, id_, suffix):
        tool = self._models["contextTool"][id_]
        suite = self._state["suite"]
        tool.set_suffix(suffix)
        suite.set_context_suffix(id_, suffix)
        self.defer_update_suite_tools()

    def on_context_tool_alias_changed(self, id_, tool, alias):
        suite = self._state["suite"]
        if alias:
            suite.alias_tool(id_, tool, alias)
        else:
            suite.unalias_tool(id_, tool)
        self.defer_update_suite_tools()

    def on_context_tool_hide_changed(self, id_, tool, hide):
        suite = self._state["suite"]
        if hide:
            suite.hide_tool(id_, tool)
        else:
            suite.unhide_tool(id_, tool)
        self.defer_update_suite_tools()

    def on_tool_updated(self):
        # TODO: block and unblock gui ?
        suite = self._state["suite"]
        suite.update_tools()

        # update tool models
        for id_ in self._state["contextName"].keys():
            conflicts = set()
            tool = self._models["contextTool"][id_]

            for exposed in tool.iter_exposed_tools():
                for entry in suite.get_alias_conflicts(exposed) or []:
                    if entry["context_name"] == id_:
                        conflicts.add(exposed)

            tool.set_conflicting(conflicts)

    def on_suite_named(self, name):
        self._state["suiteName"] = name

    def on_suite_dired(self, path):
        self._state["suiteDir"] = path

    def on_suite_commented(self, comment):
        suite = self._state["suite"]
        suite.add_description(comment)

    def on_suite_saved(self):
        self.save_suite(as_draft=False)

    def on_suite_drafted(self):
        self.save_suite(as_draft=True)

    def save_suite(self, as_draft):
        if as_draft:
            path = sweetconfig.drafts()
        else:
            path = self._state["suiteDir"]

        suite = self._state["suite"]
        name = self._state["suiteName"]

        if name:
            # rename context from id to actual name
            for id_, n in self._state["contextName"].items():
                suite.rename_context(id_, n)

            try:
                suite.save(os.path.join(path, name))
            finally:
                # restore id naming
                for id_, n in self._state["contextName"].items():
                    suite.rename_context(n, id_)
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
