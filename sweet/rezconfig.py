
import os
from rez.plugin_managers import RezPluginType, plugin_manager
ModifyList = globals()["ModifyList"]


plugin_path = ModifyList(append=[
    # The path *above* rezplugins/ directory
    os.path.dirname(__file__)
])

plugins = {
    "live_resolve": {
        "sweet": {
        },
    }
}


class LiveResolvePluginType(RezPluginType):
    """Support for live resolving suite.
    """
    type_name = "live_resolve"


plugin_manager.register_plugin_type(LiveResolvePluginType)
