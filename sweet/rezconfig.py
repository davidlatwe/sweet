
import os
ModifyList = globals()["ModifyList"]


plugin_path = ModifyList(append=[
    # The path *above* rezplugins/ directory
    os.path.dirname(__file__)
])
