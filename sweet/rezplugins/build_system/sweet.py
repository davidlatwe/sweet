
import os
import sys
from rezplugins.build_system import custom
from rez.resolved_context import ResolvedContext
from rez.config import _load_config_from_filepaths, config


class SweetBuildSystem(custom.CustomBuildSystem):

    @classmethod
    def name(cls):
        return "sweet"


def find_configs(dir_path):
    configs = list()

    while True:
        config_file = os.path.join(dir_path, "rezconfig.py")
        if os.path.isfile(config_file):
            configs.append(config_file)

        parent_dir = os.path.dirname(dir_path)
        if parent_dir == dir_path:
            break  # reach root

        dir_path = parent_dir

    return configs


def _FWD__invoke_suite_tool_alias_in_live(package_requests,
                                          context_name,
                                          tool_name,
                                          prefix_char=None,
                                          _script=None,
                                          _cli_args=None):
    # Load configs
    configs = find_configs(os.getcwd())
    overrides, _ = _load_config_from_filepaths(configs)
    for key, value in overrides.items():
        config.override(key, value)

    suite_path = os.path.dirname(os.path.dirname(_script))
    context = ResolvedContext(package_requests)

    from rez.wrapper import Wrapper
    w = Wrapper.__new__(Wrapper)
    w._init(suite_path, context_name, context, tool_name, prefix_char)
    retcode = w.run(*(_cli_args or []))
    sys.exit(retcode)


def register_plugin():
    return SweetBuildSystem
