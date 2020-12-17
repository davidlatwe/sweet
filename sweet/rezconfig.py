
import os
ModifyList = globals()["ModifyList"]


# Location: install
__install_uri = os.getenv("MONGOZARK_INSTALL_DB", "mongodb://localhost:27017")
__install_loc = os.getenv("MONGOZARK_INSTALL_LOC", "mongozark@rez.install")

# Location: release
__release_uri = os.getenv("MONGOZARK_RELEASE_DB", "mongodb://localhost:27017")
__release_loc = os.getenv("MONGOZARK_RELEASE_LOC", "mongozark@rez.release")


packages_path = ModifyList(append=[
    __install_loc,
    __release_loc,
])


plugins = {
    "package_repository": {
        "mongozark": {
            # rez package path
            "rez": {
                "install": __install_loc,
                "release": __release_loc
            },
            # database uri
            "uri": {
                "install": __install_uri,
                "release": __release_uri,
            },
            # database settings
            "mongodb": {
                "select_timeout": int(
                    # 3 sec
                    os.getenv("MONGOZARK_DB_SELECT_TIMEOUT", "3000")
                ),
            },
        },
    }
}


plugin_path = ModifyList(append=[
    # The path *above* rezplugins/ directory
    os.path.dirname(__file__)
])

# Turn this on if plugin not loaded.
# Or set environment var `REZ_DEBUG_PLUGINS=1`
debug_plugins = False
