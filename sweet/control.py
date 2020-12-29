
import os
from .vendor.Qt5 import QtCore
from . import _rezapi as rez
from .search.model import PackageModel
from .solve.model import ResolvedPackageModel, EnvironmentModel
from .sphere.model import ToolModel
from .suite.model import SavedSuiteModel, CapedSavedSuiteModel
from . import sweetconfig, util


class State(dict):

    def __init__(self, storage):
        super(State, self).__init__({
            "suite": rez.SweetSuite(),
            "suiteRoot": "",
            "suiteName": "",
            "suiteDescription": "",
            "contextName": dict(),
            "contextRequests": dict(),  # success requests history (not used)
            "suiteSaveRoots": sweetconfig.suite_roots(),
            "recentSavedSuites": None,
            "rootKey": None,

            # Preferences, these will be updated on preference changed
            "recentSuiteCount": int(storage.value("recentSuiteCount", 10)),
            "suiteOpenAs": storage.value("suiteOpenAs", "Ask"),
        })

        self._storage = storage

    def store(self, key, value):
        """Write to persistent storage

        Arguments:
            key (str): Name of variable
            value (object): Any datatype

        """
        self[key] = value
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
        true = ["2", "1", "true", True, 1, 2]
        false = ["0", "false", False, 0]

        if value in true:
            value = True

        if value in false:
            value = False

        if value and str(value).isnumeric():
            value = float(value)

        return value


class Controller(QtCore.QObject):
    suite_changed = QtCore.Signal(str, object, object)
    context_removed = QtCore.Signal(str)
    context_loaded = QtCore.Signal(dict, list)

    def __init__(self, storage, parent=None):
        super(Controller, self).__init__(parent=parent)

        state = State(storage=storage)

        timers = {
            "toolUpdate": QtCore.QTimer(self),
            "packageSearch": QtCore.QTimer(self),
            "savedSuites": QtCore.QTimer(self),
            "maxRecent": QtCore.QTimer(self),
        }

        models = {
            "package": PackageModel(),
            "recent": CapedSavedSuiteModel(max_=state["recentSuiteCount"]),
            # models per suite saving root
            "saved": {k: SavedSuiteModel() for k in state["suiteSaveRoots"]},
            # models per context
            "contextPackages": dict(),
            "contextEnvironment": dict(),
            "contextTool": dict(),
        }

        timers["packageSearch"].timeout.connect(self.on_package_searched)
        timers["savedSuites"].timeout.connect(self.on_saved_suite_listed)
        timers["toolUpdate"].timeout.connect(self.on_tool_updated)
        timers["maxRecent"].timeout.connect(self.on_max_recent_changed)

        self._state = state
        self._timers = timers
        self._models = models

    @property
    def state(self):  # state is also like a model and good to be exposed
        return self._state

    @property
    def models(self):
        return self._models

    def default_root(self):
        return self._state["suiteSaveRoots"][sweetconfig.default_root]

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

    def defer_list_saved_suites(self, on_time=50):
        timer = self._timers["savedSuites"]
        timer.setSingleShot(True)
        timer.start(on_time)

    def defer_update_suite_tools(self, on_time=500):
        timer = self._timers["toolUpdate"]
        timer.setSingleShot(True)
        timer.start(on_time)

    def defer_change_max_recent(self, on_time=100):
        timer = self._timers["maxRecent"]
        timer.setSingleShot(True)
        timer.start(on_time)

    def on_package_searched(self):
        self._models["package"].reset(self.iter_packages())

    def on_saved_suite_listed(self):
        # TODO: iter each in separate threads
        self._models["recent"].add_files(self.iter_recent_suites())
        for key, model in self._models["saved"].items():
            root = self._state["suiteSaveRoots"][key]
            model.add_files(self.iter_suites_in_root(root))

    def on_max_recent_changed(self):
        value = self._state["recentSuiteCount"]
        self._models["recent"].change_max_row(value)

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
        self.remove_context(id_)
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
        suite.unalias_tool(id_, tool)
        if alias:
            suite.alias_tool(id_, tool, alias)
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

    def on_suite_rooted(self, name):
        root = self._state["suiteSaveRoots"][name]
        self._state["rootKey"] = name
        self._state["suiteRoot"] = root
        self.suite_changed.emit(root, None, None)

    def on_suite_commented(self, comment):
        self._state["suiteDescription"] = comment

    def on_suite_saved(self):
        self.save_suite()

    def on_suite_loaded(self, path, as_import):
        self.load_suite(path, as_import)

    def remove_context(self, id_):
        self.context_removed.emit(id_)

        self._models["contextTool"].pop(id_)
        self._models["contextPackages"].pop(id_)
        self._models["contextEnvironment"].pop(id_)
        self._state["contextName"].pop(id_)
        self._state["contextRequests"].pop(id_)

        suite = self._state["suite"]
        suite.remove_context(id_)

    def save_suite(self):
        suite = self._state["suite"]
        root = self._state["suiteRoot"]
        name = self._state["suiteName"]
        comment = self._state["suiteDescription"]

        if not root or not name:
            print("Naming suite first.")
            return

        path = util.normpath(os.path.join(root, name))

        # rename context from id to actual name
        for id_, n in self._state["contextName"].items():
            suite.rename_context(id_, n)

        suite.add_description(comment)
        try:
            suite.save(path)
            suite.load_path = os.path.realpath(path)
            self.update_suite_lists(root, name)
            self.callback_on_suite_saved(path)

        finally:
            # restore id naming
            for id_, n in self._state["contextName"].items():
                suite.rename_context(n, id_)

    def load_suite(self, path, as_import):
        suite = rez.SweetSuite.load(path)

        self.clear_suite()
        names = self._state["contextName"]
        tools = self._models["contextTool"]

        for ctx_name in suite.sorted_context_names():
            context = suite.context(ctx_name)
            requested = context.requested_packages()
            prefix = suite.read_context(ctx_name, "prefix", default="")
            suffix = suite.read_context(ctx_name, "suffix", default="")
            hidden = suite.read_context(ctx_name, "hidden_tools")
            aliases = suite.read_context(ctx_name, "tool_aliases")
            # TODO: get filter, timestamp, building from context

            ctx_data = {
                "name": ctx_name,
                "prefix": prefix,
                "suffix": suffix,
            }
            requests = [str(r) for r in requested]
            self.context_loaded.emit(ctx_data, requests)

            id_ = next(i for i in names if names[i] == ctx_name)
            tools[id_].load(hidden, aliases)

        if as_import:
            root = ""
            name = ""
        else:
            root, name = os.path.split(path)
            self._state["suite"].load_path = os.path.realpath(path)

        self._state["suiteRoot"] = root
        self.suite_changed.emit(root, name, suite.description)

    def clear_suite(self):
        for id_ in list(self._state["contextName"].keys()):
            self.remove_context(id_)

        default_root = self.default_root()
        self.suite_changed.emit(default_root, "", "")
        self._state["suite"] = rez.SweetSuite()

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

    def update_suite_lists(self, root, name):
        state = self._state
        models = self._models

        newly_saved = util.normpath(os.path.join(root, name, "suite.yaml"))
        valid_path = [util.normpath(p) for p in self.iter_recent_suites()]

        if newly_saved in valid_path:
            valid_path.remove(newly_saved)
        valid_path.insert(0, newly_saved)

        # store paths with no trimming just yet, for preference changing
        state.store("recentSavedSuites", os.pathsep.join(valid_path))
        # trim down in view
        models["recent"].add_files(valid_path, clear=True)

        for key, _root in state["suiteSaveRoots"].items():
            if _root == root:
                models["saved"][key].add_files([newly_saved], clear=False)
                break

    def iter_recent_suites(self, fetch_all=True):
        state = self._state
        recent = state.retrieve("recentSavedSuites", "").split(os.pathsep)
        max_count = -1 if fetch_all else self._state["recentSuiteCount"]
        count = 0

        for filepath in recent:
            if not filepath or not os.path.isfile(filepath):
                continue
            yield filepath

            count += 1
            if count == max_count:
                break

    def iter_suites_in_root(self, root):
        if not os.path.isdir(root):
            return

        for dir_name in os.listdir(root):
            filepath = os.path.join(root, dir_name, "suite.yaml")
            if os.path.isfile(filepath):
                yield filepath

    def callback_on_suite_saved(self, suite_dir):
        sweetconfig.on_suite_saved_callback(suite_dir)
