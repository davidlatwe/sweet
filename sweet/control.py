
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
            "context": dict(),
        }

        timers = {
            "toolUpdate": QtCore.QTimer(self),
            "packageSearch": QtCore.QTimer(self),
        }

        models = {
            "package": PackageModel(),
            "tool": ToolModel(),
        }

        timers["toolUpdate"].timeout.connect(self.on_tool_updated)
        timers["packageSearch"].timeout.connect(self.on_package_searched)

        self._state = state
        self._timers = timers
        self._models = models

    @property
    def state(self):
        return self._state

    @property
    def models(self):
        return self._models

    def search_packages(self, on_time=50):
        timer = self._timers["packageSearch"]
        timer.setSingleShot(True)
        timer.start(on_time)

    def update_suite_tools(self, on_time=500):
        timer = self._timers["toolUpdate"]
        timer.setSingleShot(True)
        timer.start(on_time)

    def on_tool_updated(self):
        # TODO: block and unblock gui ?
        # TODO: block suite save if has conflicts
        conflicts = self._data["suite"].get_conflicting_aliases()
        # update tool models
        for context_w in self._contexts.values():
            context_w.set_conflicting(conflicts)

    def on_package_searched(self):
        self._models["package"].reset(self.iter_packages())

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
